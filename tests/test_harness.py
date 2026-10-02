"""검수 Harness 검사 (작업 Graph Q3 기준별 테스트).

깨끗한 고정 데이터는 모든 정적 검사를 통과하고, 심은 결함은 정해진 검사가 정확히 잡는지(기준선 + 변이)를 본다.
저장소 파일은 쓰지 않는다 — 결함 데이터는 임시 폴더에 매니페스트의 edits 를 적용해 만든다.
"""
import contextlib
import copy
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness import luau, run, source  # noqa: E402
from harness.checks import REGISTRY, i18n, math_claims  # noqa: E402

FIXTURES = ROOT / "harness" / "fixtures"
CLEAN = FIXTURES / "clean"
MANIFEST = run.load_manifest()
RULES = source.load_rules(ROOT)
GRAPH = json.loads((ROOT / "graph.json").read_text(encoding="utf-8"))
DEFECTS = {d["id"]: d for d in MANIFEST["defects"]}
# 작업 Graph Q3-C1 이 이름으로 든 결함 종류 전부 — 매니페스트의 결함이 하나도 빠짐없이 덮어야 한다
REQUIRED_CLASSES = {"클라이언트가 보상을 정하는 코드", "중복 보상", "검증 없는 원격 입력", "끊긴 번역 키", "넘치는 긴 번역문", "번역된 수식",
                    "코드 속 하드코딩 문구", "틀린 수학 대사", "조건이 빠진 수학 명제", "어려운 문장", "금지어", "무작위 보상 코드",
                    "유료 보상 코드", "URL 문자열", "런타임 외부 호출(LLM)", "필터 없는 자유 입력", "커스텀 필드 개인정보",
                    "허용 밖 분석 이벤트", "클라이언트 분석 전송"}
# 매니페스트와 따로 적은 결함표 — id → (종류, 잡아야 할 검사, 기대 진단 문구 조각).
# 결함을 지우거나 기대 검사·진단을 바꾸면 테스트가 실패한다 (리뷰 R-Q3 3·4·11차)
EXPECTED_DEFECTS = {
    "D-absolute-path": ("절대 경로를 쓴 Rojo 프로젝트", ("analytics.calls", "i18n.do_not_translate", "i18n.hardcoded_text", "i18n.length_budget", "i18n.missing_key", "math.conditions", "math.truth", "safety.banned_terms", "safety.external_call", "safety.free_text", "safety.random_or_paid_reward", "safety.url", "server.duplicate_reward", "server.remote_cooldown", "server.remote_validation", "server.reward_after_verdict", "server.reward_authority", "text.readability"), "Rojo 경로(StarterPlayer/StarterPlayerScripts/G"),
    "D-alias-grant-in-handler": ("처리 함수 안의 별칭 보상", ("server.duplicate_reward", "server.reward_after_verdict"), "보상 reward.explorer_card(m.gate_open)를 주는 호출이"),
    "D-analytics-alias": ("별칭으로 부른 허용 밖 분석 이벤트", ("analytics.calls",), "이벤트 player_profile 가 허용 목록(specs/analytics/e"),
    "D-analytics-computed-event": ("어디서 왔는지 알 수 없는 분석 이벤트", ("analytics.calls",), "분석 모듈이 LogCustomEvent 의 이벤트 이름 자리에 'getEvent"),
    "D-coordinate-fractional-move": ("대사에 없는 분수 이동량", ("math.truth",), "수만으로는 대사와 묶을 수 없는 명제다"),
    "D-analytics-platform-alias-inside": ("분석 모듈 안의 플랫폼 전송 별칭", ("analytics.calls",), "다른 이름(send)에 담는다 — 모듈 안에서는 직접 불러야"),
    "D-remote-receiver-unresolved": ("값을 알 수 없는 변수에 건 원격 처리", ("server.remote_validation",), "연결 대상 evt 가 멤버 경로가 아니다"),
    "D-reward-module-impostor": ("이름만 보상 모듈인 Script", ("server.reward_authority",), "보상 모듈과 같은 이름인데 정해진 자리"),
    "D-dynamic-service-call": ("값을 알 수 없는 서비스·메서드 호출", ("safety.external_call",), "어떤 서비스를 가져오는지 알 수 없다"),
    "D-client-grant-call": ("클라이언트가 부른 보상 지급", ("server.reward_authority",), "클라이언트가 볼 수 있는 코드가 보상 지급 RewardService.grant 를 부른다"),
    "D-ui-bracket-unresolved-property": ("값을 알 수 없는 UI 속성 이름", ("i18n.hardcoded_text",), "속성 이름을 값을 알 수 없는 방식으로 고른다"),
    "D-conditions-not-a-table": ("표가 아닌 조건", ("math.conditions",), "조건(conditions)은 '이름: 값' 표여야 한다"),
    "D-bracket-property-non-instance": ("비인스턴스 객체의 알 수 없는 속성 이름", ("i18n.hardcoded_text",), "속성 이름을 값을 알 수 없는 방식으로 고른다"),
    "D-analytics-module-impostor": ("이름만 분석 모듈인 Script", ("analytics.calls",), "정해진 자리(src/server/Analytics.luau)의 ModuleScript 가 아니다"),
    "D-random-alias-dynamic-member": ("난수 원천 별칭의 동적 멤버", ("safety.random_or_paid_reward",), "난수 원천 R 의 멤버를 값을 알 수 없는 방식으로 고른다"),
    "D-project-path-not-a-string": ("글자가 아닌 Rojo $path", ("analytics.calls", "i18n.do_not_translate", "i18n.hardcoded_text", "i18n.length_budget", "i18n.missing_key", "math.conditions", "math.truth", "safety.banned_terms", "safety.external_call", "safety.free_text", "safety.random_or_paid_reward", "safety.url", "server.duplicate_reward", "server.remote_cooldown", "server.remote_validation", "server.reward_after_verdict", "server.reward_authority", "text.readability"), "$path 는 글자여야 한다"),
    "D-dynamic-member-handler": ("동적 멤버에 대입한 원격 처리", ("server.remote_validation",), "에 처리 함수를 대입했다"),
    "D-analytics-dynamic-platform-member": ("분석 모듈 안의 동적 플랫폼 멤버", ("analytics.calls", "safety.external_call"), "어떤 전송 함수인지 검사할 수 없다"),
    "D-ui-text-from-bracket-call": ("대괄호 멤버로 부른 UI 문구", ("i18n.hardcoded_text",), "허용된 문구 키 호출이 아닌 함수의 결과를 넣는다"),
    "D-analytics-concat-event": ("이어 붙인 분석 이벤트 이름", ("analytics.calls",), "분석 모듈이 LogCustomEvent 의 이벤트 이름 자리에 'eventNam"),
    "D-analytics-dot-call": ("점 표기로 부른 플랫폼 분석 API", ("analytics.calls",), "분석 모듈이 LogCustomEvent 에 정해진 값 ['player_profi"),
    "D-analytics-method-alias": ("전송 함수를 담은 이름으로 보낸 분석", ("analytics.calls",), "이벤트 player_profile 가 허용 목록(specs/analytics/e"),
    "D-analytics-module-constant-event": ("분석 모듈이 상수 변수로 보낸 이벤트", ("analytics.calls",), "분석 모듈이 LogCustomEvent 에 정해진 값 ['not_allowed'"),
    "D-analytics-module-literal": ("분석 모듈이 글자 그대로 보내는 이벤트", ("analytics.calls",), "분석 모듈이 LogCustomEvent 에 정해진 값 ['player_profi"),
    "D-analytics-module-pii": ("분석 모듈 안의 개인정보", ("analytics.calls",), "분석 모듈이 플레이어 개인정보 속성 Name 를 쓴다 (INV-10)"),
    "D-analytics-pii": ("커스텀 필드 개인정보", ("analytics.calls",), "필드 play_mode 의 값 'player . Name' 이 열거형 글자 그대"),
    "D-analytics-two-step-alias": ("두 단계로 넘긴 분석 전송 함수", ("analytics.calls",), "이벤트 player_profile 가 허용 목록(specs/analytics/e"),
    "D-analytics-unknown-event": ("허용 밖 분석 이벤트", ("analytics.calls",), "이벤트 player_profile 가 허용 목록(specs/analytics/e"),
    "D-anonymous-reward-helper": ("익명 함수에 담은 보상 도우미", ("server.reward_after_verdict",), "원격 처리가 서버 판정(MissionService.coordinateMove ·"),
    "D-badge-bypass": ("보상 모듈을 거치지 않은 자격 발급", ("server.reward_authority",), "보상 모듈 밖 서버 코드가 보상·저장 권한 BadgeService 를 쓴다"),
    "D-banned-term": ("금지어", ("safety.banned_terms",), "resp.gate_open[Source] 금지어 ['입국', '심사']"),
    "D-bare-number-math": ("명제 없는 숫자 수학 대사", ("math.truth",), "label.extra.sum: 수학이 든 대사인데 명제가 없다"),
    "D-bracket-grant": ("대괄호로 부른 보상", ("server.duplicate_reward",), "보상 reward.explorer_card(m.gate_open)를 주는 호출이"),
    "D-bracket-remote": ("대괄호로 등록한 원격 처리", ("server.remote_cooldown", "server.remote_validation"), "원격 이벤트 처리가 Cooldown.allow 를 거치지 않는다 (연타·자동 반"),
    "D-bracket-ui-text": ("대괄호로 넣은 UI 문구", ("i18n.hardcoded_text",), "UI 글자 속성 .Text 에 문구 'Ready' 를 바로 넣었다"),
    "D-broken-claims": ("망가진 명제 파일", ("analytics.calls", "i18n.do_not_translate", "i18n.hardcoded_text", "i18n.length_budget", "i18n.missing_key", "math.conditions", "math.truth", "safety.banned_terms", "safety.external_call", "safety.free_text", "safety.random_or_paid_reward", "safety.url", "server.duplicate_reward", "server.remote_cooldown", "server.remote_validation", "server.reward_after_verdict", "server.reward_authority", "text.readability"), "content/math_claims.yaml: 읽지 못했다 (ScannerErr"),
    "D-broken-key": ("끊긴 번역 키", ("i18n.missing_key",), "문구 키 goal.signal_two 가 LocalizationTable 에 없"),
    "D-claimonce-not-called": ("호출하지 않은 중복 방지", ("server.duplicate_reward",), "grant 가 맨 앞에서 'if not claimOnce(…) then retu"),
    "D-client-analytics": ("클라이언트 분석 전송", ("analytics.calls",), "분석 모듈을 거치지 않고 AnalyticsService 를 쓴다"),
    "D-client-completion": ("클라이언트 완료 신고로 보상", ("server.reward_after_verdict",), "원격 처리가 서버 판정(MissionService.coordinateMove ·"),
    "D-client-reward": ("클라이언트가 보상을 정하는 코드", ("server.reward_authority",), "클라이언트 코드가 보상·저장 권한 leaderstats 를 쓴다"),
    "D-concat-authority": ("문자열을 쪼개 숨긴 보상 권한", ("server.reward_authority",), "클라이언트 코드가 보상·저장 권한 leaderstats 를 쓴다"),
    "D-concat-free-text": ("문자열을 쪼개 숨긴 자유 입력", ("safety.free_text",), "자유 입력 TextBox 를 쓴다"),
    "D-concat-url": ("문자열을 쪼개 숨긴 외부 링크", ("i18n.hardcoded_text", "safety.url"), "코드에 화면 문구 'https://example.com/' 가 있다"),
    "D-content-mapped": ("검사 입력 폴더를 Rojo 에 실음", ("analytics.calls", "i18n.do_not_translate", "i18n.hardcoded_text", "i18n.length_budget", "i18n.missing_key", "math.conditions", "math.truth", "safety.banned_terms", "safety.external_call", "safety.free_text", "safety.random_or_paid_reward", "safety.url", "server.duplicate_reward", "server.remote_cooldown", "server.remote_validation", "server.reward_after_verdict", "server.reward_authority", "text.readability"), "Rojo 경로 content 는 소스 폴더(src/) 안이어야 한다"),
    "D-contract-off-canonical": ("정본 값과 다른 입력 계약", ("server.remote_validation",), "원격 계약 SignalRemote.x: 범위(-9~9)가 정본 값 cv.coor"),
    "D-cooldown-with-extra-condition": ("다른 조건과 섞인 쿨다운", ("server.remote_cooldown",), "쿨다운 결과로 멈추지 않는다"),
    "D-double-mapped-file": ("같은 파일을 두 곳에 싣는 매핑", ("analytics.calls", "i18n.do_not_translate", "i18n.hardcoded_text", "i18n.length_budget", "i18n.missing_key", "math.conditions", "math.truth", "safety.banned_terms", "safety.external_call", "safety.free_text", "safety.random_or_paid_reward", "safety.url", "server.duplicate_reward", "server.remote_cooldown", "server.remote_validation", "server.reward_after_verdict", "server.reward_authority", "text.readability"), "src/shared/Localization.csv: 같은 파일을 Replicat"),
    "D-double-negated-cooldown": ("두 번 뒤집은 쿨다운", ("server.remote_cooldown",), "쿨다운 결과로 멈추지 않는다"),
    "D-duplicate-reward": ("중복 보상", ("server.duplicate_reward", "server.reward_after_verdict"), "보상 reward.explorer_card(m.gate_open)를 주는 호출이"),
    "D-dynamic-analytics-member": ("값을 알 수 없는 분석 멤버", ("analytics.calls",), "분석 모듈 Analytics 의 멤버를 값을 알 수 없는 방식으로 고른다"),
    "D-dynamic-authority-member": ("동적 멤버로 쓴 보상 권한", ("safety.external_call", "server.reward_authority"), "값을 알 수 없는 방식으로"),
    "D-dynamic-remote-member": ("변수로 만든 대괄호 원격 등록", ("server.remote_cooldown", "server.remote_validation"), "원격 이벤트 처리가 Cooldown.allow 를 거치지 않는다 (연타·자동 반"),
    "D-dynamic-reward-member": ("값을 알 수 없는 보상 멤버", ("server.duplicate_reward",), "보상 모듈 RewardService 의 멤버를 값을 알 수 없는 방식으로 고른다"),
    "D-dynamic-text-member": ("변수로 고른 문구 함수", ("i18n.missing_key",), "문구 키 goal.missing 가 LocalizationTable 에 없다"),
    "D-dynamic-text-member-unresolved": ("값을 알 수 없는 문구 멤버", ("i18n.hardcoded_text", "i18n.missing_key"), "UI 글자 속성 .Text 에 허용된 문구 키 호출이 아닌 함수의 결과를 넣는다"),
    "D-else-reward": ("판정의 else 가지에서 보상", ("server.reward_after_verdict",), "원격 처리가 서버 판정(MissionService.coordinateMove ·"),
    "D-equals-false-verdict": ("판정이 거짓(== false)인 가지에서 보상", ("server.reward_after_verdict",), "원격 처리가 서버 판정(MissionService.coordinateMove ·"),
    "D-fraction-line-untied": ("대사와 묶이지 않은 분수 계수", ("math.truth",), "claim.line.point: 분수 계수는 수로 대사와 묶을 수 없다"),
    "D-free-text": ("필터 없는 자유 입력", ("safety.free_text",), "자유 입력 TextBox 를 쓴다"),
    "D-ftp-url": ("다른 스킴의 외부 링크", ("safety.url",), "resp.gate_open[Source] URL 이나 도메인 'ftp://' 이"),
    "D-funnel-as-custom": ("퍼널 단계를 사용자 정의로 전송", ("analytics.calls",), "gate_opened 는 온보딩 퍼널 단계인데 다른 전송 함수(log)로 보낸다"),
    "D-hard-sentence": ("어려운 문장", ("text.readability",), "hint.slope.compare[Source] 문장 폭이 110 다"),
    "D-hardcoded-text": ("코드 속 하드코딩 문구", ("i18n.hardcoded_text",), "UI 글자 속성 .Text 에 문구 '루미를 신호 칸으로 보내자' 를 바로 넣었"),
    "D-ignored-cooldown": ("결과를 버리는 쿨다운", ("server.remote_cooldown",), "쿨다운 결과로 멈추지 않는다"),
    "D-impossible-range": ("성립할 수 없는 범위 조건", ("server.remote_validation",), "원격 입력 x 의 범위를 처리 전에 검사하지 않는다 (INV-4 타입·범위)"),
    "D-inclusive-bound": ("경계를 하나 더 거르는 범위 가드", ("server.remote_validation",), "원격 입력 x 의 범위 가드(-1.0~1.0)가 계약(-2~2)과 다르다"),
    "D-indirect-reward-helper": ("간접 도우미를 거친 보상", ("server.reward_after_verdict",), "원격 처리가 서버 판정(MissionService.coordinateMove ·"),
    "D-interpolated-string": ("보간 문자열 안의 코드", ("analytics.calls", "i18n.do_not_translate", "i18n.hardcoded_text", "i18n.length_budget", "i18n.missing_key", "math.conditions", "math.truth", "safety.banned_terms", "safety.external_call", "safety.free_text", "safety.random_or_paid_reward", "safety.url", "server.duplicate_reward", "server.remote_cooldown", "server.remote_validation", "server.reward_after_verdict", "server.reward_authority", "text.readability"), "보간 문자열(`…{…}`)은 안의 코드를 검사할 수 없다"),
    "D-inverted-cooldown": ("뒤집힌 쿨다운 조건", ("server.remote_cooldown",), "쿨다운 결과로 멈추지 않는다"),
    "D-late-cooldown": ("처리 뒤에 하는 쿨다운", ("server.remote_cooldown",), "쿨다운 결과로 멈추지 않는다"),
    "D-late-guard": ("입력을 쓴 뒤에 하는 검증", ("server.remote_validation",), "원격 입력 x 의 형식 검사가 처리를 시작한 뒤에 있다"),
    "D-llm-call": ("런타임 외부 호출(LLM)", ("safety.external_call",), "런타임 외부 호출·생성형 AI HttpService 를 쓴다"),
    "D-long-translation": ("넘치는 긴 번역문", ("i18n.length_budget",), "goal.signal_2[qps-ploc] 폭 52"),
    "D-mapped-outside-src": ("Rojo 가 src 밖을 가리키는 매핑", ("analytics.calls", "i18n.do_not_translate", "i18n.hardcoded_text", "i18n.length_budget", "i18n.missing_key", "math.conditions", "math.truth", "safety.banned_terms", "safety.external_call", "safety.free_text", "safety.random_or_paid_reward", "safety.url", "server.duplicate_reward", "server.remote_cooldown", "server.remote_validation", "server.reward_after_verdict", "server.reward_authority", "text.readability"), "Rojo 경로 ui 는 소스 폴더(src/) 안이어야 한다"),
    "D-missing-condition": ("조건이 빠진 수학 명제", ("math.conditions",), "claim.slope.example: 조건 run_nonzero 가 빠졌다 (E"),
    "D-missing-contract": ("계약 없는 원격 입력", ("server.remote_validation",), "원격 SignalRemote 의 입력 계약이 content/remote_cont"),
    "D-model-textbox": ("데이터 파일로 만든 자유 입력", ("safety.free_text",), "src/client/Answer.model.json 데이터 파일이 자유 입력 T"),
    "D-negated-verdict": ("판정이 거짓인 가지에서 보상", ("server.reward_after_verdict",), "원격 처리가 서버 판정(MissionService.coordinateMove ·"),
    "D-nested-guard": ("중첩 조건 안에서만 하는 검증", ("server.remote_validation",), "원격 입력 x 를 막는 형태의 typeof 검사로 거르지 않는다"),
    "D-nonblocking-typeof": ("막지 않는 typeof 검사", ("server.remote_validation",), "원격 입력 x 를 막는 형태의 typeof 검사로 거르지 않는다"),
    "D-one-sided-range": ("한쪽만 보는 범위 조건", ("server.remote_validation",), "원격 입력 x 의 범위를 처리 전에 검사하지 않는다 (INV-4 타입·범위)"),
    "D-paid-item": ("유료 보상 코드", ("safety.random_or_paid_reward",), "결제·구독 조건 MarketplaceService 를 쓴다 (DEC-5 결정 전"),
    "D-platform-api-alias": ("플랫폼 전송 함수를 담은 이름", ("analytics.calls",), "분석 모듈을 거치지 않고 AnalyticsService 를 쓴다"),
    "D-player-alias-dynamic-authority": ("플레이어 별칭의 동적 권한 접근", ("i18n.hardcoded_text", "server.reward_authority"), "값을 알 수 없는 방식으로 고른다"),
    "D-player-alias-pii": ("플레이어 별칭으로 넣은 개인정보", ("analytics.calls",), "분석 모듈이 플레이어 개인정보 속성 Name 를 쓴다 (INV-10)"),
    "D-premium-gate": ("구독 회원 전용 보상", ("safety.random_or_paid_reward",), "결제·구독 조건 HasRobloxSubscription 를 쓴다 (DEC-5 결"),
    "D-project-tree-not-object": ("구조가 틀린 Rojo 프로젝트", ("analytics.calls", "i18n.do_not_translate", "i18n.hardcoded_text", "i18n.length_budget", "i18n.missing_key", "math.conditions", "math.truth", "safety.banned_terms", "safety.external_call", "safety.free_text", "safety.random_or_paid_reward", "safety.url", "server.duplicate_reward", "server.remote_cooldown", "server.remote_validation", "server.reward_after_verdict", "server.reward_authority", "text.readability"), "default.project.json: tree 는 객체여야 한다"),
    "D-random-alias-chain": ("별칭으로 부른 난수", ("safety.random_or_paid_reward",), "난수를 쓴다"),
    "D-random-helper": ("도우미 모듈로 옮긴 무작위 보상", ("safety.random_or_paid_reward",), "난수를 쓴다"),
    "D-random-reward": ("무작위 보상 코드", ("safety.random_or_paid_reward",), "난수를 쓴다"),
    "D-range-before-type": ("타입보다 앞선 범위 검사", ("server.remote_validation",), "원격 입력 x 의 형식 검사가 범위 검사보다 뒤에 있다"),
    "D-reassigned-grid": ("다시 묶인 범위 상수", ("server.remote_validation",), "원격 입력 x 의 범위 가드(None~None)가 계약(-2~2)과 다르다"),
    "D-reassigned-grid-after-block": ("블록 끝 뒤에 다시 묶인 상수", ("server.remote_validation",), "원격 입력 x 의 범위 가드(None~None)가 계약(-2~2)과 다르다"),
    "D-remote-no-cooldown": ("쿨다운 없는 원격 입력", ("server.remote_cooldown",), "원격 이벤트 처리가 Cooldown.allow 를 거치지 않는다 (연타·자동 반"),
    "D-remotefunction": ("검증 없는 RemoteFunction", ("server.remote_cooldown", "server.remote_validation"), "원격 이벤트 처리가 Cooldown.allow 를 거치지 않는다 (연타·자동 반"),
    "D-reward-alias": ("별칭으로 부른 중복 보상", ("server.duplicate_reward",), "보상 reward.explorer_card(m.gate_open)를 주는 호출이"),
    "D-reward-bypass": ("보상 모듈을 거치지 않은 지급", ("server.reward_authority",), "보상 모듈 밖 서버 코드가 보상·저장 권한 leaderstats 를 쓴다"),
    "D-same-service-double-map": ("같은 서비스 안의 중복 매핑", ("analytics.calls", "i18n.do_not_translate", "i18n.hardcoded_text", "i18n.length_budget", "i18n.missing_key", "math.conditions", "math.truth", "safety.banned_terms", "safety.external_call", "safety.free_text", "safety.random_or_paid_reward", "safety.url", "server.duplicate_reward", "server.remote_cooldown", "server.remote_validation", "server.reward_after_verdict", "server.reward_authority", "text.readability"), "src/shared/Localization.csv: 같은 파일을 Replicat"),
    "D-term-line-without-claim": ("숫자 없는 용어 대사에 명제 없음", ("math.truth",), "hint.slope.extra: 수학이 든 대사인데 명제가 없다"),
    "D-text-alias": ("별칭으로 부른 끊긴 번역 키", ("i18n.missing_key",), "문구 키 goal.missing 가 LocalizationTable 에 없다"),
    "D-text-alias-chain": ("두 단계로 넘긴 문구 함수", ("i18n.missing_key",), "문구 키 goal.missing 가 LocalizationTable 에 없다"),
    "D-text-function-alias": ("문구 함수를 담은 이름으로 쓴 끊긴 키", ("i18n.missing_key",), "문구 키 goal.missing 가 LocalizationTable 에 없다"),
    "D-textgenerator": ("런타임 생성형 AI 대화(TextGenerator)", ("safety.external_call",), "런타임 외부 호출·생성형 AI TextGenerator 를 쓴다"),
    "D-translated-math": ("번역된 수식", ("i18n.do_not_translate",), "label.coordinate.line[qps-ploc] 번역 금지 조각이 원문"),
    "D-two-step-grant-alias": ("두 단계로 넘긴 보상 별칭", ("server.duplicate_reward", "server.reward_after_verdict"), "보상 reward.explorer_card(m.gate_open)를 주는 호출이"),
    "D-ui-text-from-function": ("함수가 만든 UI 문구", ("i18n.hardcoded_text",), "UI 글자 속성 .Text 에 허용된 문구 키 호출이 아닌 함수의 결과를 넣는다"),
    "D-ui-text-from-other-function": ("허용 밖 함수가 만든 UI 문구", ("i18n.hardcoded_text",), "UI 글자 속성 .Text 에 허용된 문구 키 호출이 아닌 함수의 결과를 넣는다"),
    "D-ui-text-literal": ("UI 글자 속성에 바로 넣은 문구", ("i18n.hardcoded_text",), "UI 글자 속성 .Text 에 문구 'Start' 를 바로 넣었다"),
    "D-ui-text-variable": ("변수로 넣은 UI 문구", ("i18n.hardcoded_text",), "UI 글자 속성 .Text 에 문구 'Open_Gate' 를 바로 넣었다"),
    "D-unknown-analytics-function": ("분석 모듈의 모르는 함수", ("analytics.calls",), "분석 모듈의 모르는 함수 raw 를 부른다"),
    "D-unknown-remote-member": ("값을 알 수 없는 멤버에 건 원격 처리", ("server.remote_validation",), "값을 알 수 없는 멤버에 처리 함수를 이었다"),
    "D-unranged-remote": ("범위를 검사하지 않는 원격 입력", ("server.remote_validation",), "원격 입력 x 의 범위를 처리 전에 검사하지 않는다 (INV-4 타입·범위)"),
    "D-unreadable-model": ("검사할 수 없는 이진 모델", ("analytics.calls", "i18n.do_not_translate", "i18n.hardcoded_text", "i18n.length_budget", "i18n.missing_key", "math.conditions", "math.truth", "safety.banned_terms", "safety.external_call", "safety.free_text", "safety.random_or_paid_reward", "safety.url", "server.duplicate_reward", "server.remote_cooldown", "server.remote_validation", "server.reward_after_verdict", "server.reward_authority", "text.readability"), "src/shared/Widget.rbxm: Rojo 가 싣는 이진 모델이라 검사"),
    "D-unresolved-ui-text": ("UI 로 흘러가는 알 수 없는 조립 글자", ("i18n.hardcoded_text",), "UI 글자 속성 .Text 에 허용된 문구 키 호출이 아닌 함수의 결과를 넣는다"),
    "D-untied-boolean-claim": ("대사와 묶이지 않은 참·거짓 명제", ("math.truth",), "claim.line.point: 수만으로는 대사와 묶을 수 없는 명제다"),
    "D-untied-comparison": ("대사와 묶이지 않은 비교 명제", ("math.truth",), "claim.slope.compare: 수만으로는 대사와 묶을 수 없는 명제다"),
    "D-untied-fraction": ("대사와 묶이지 않은 분수 값", ("math.truth",), "claim.slope.example: 수만으로는 대사와 묶을 수 없는 명제다"),
    "D-untied-math-line": ("명제 없는 수학 대사", ("math.truth",), "label.extra.line: 수학이 든 대사인데 명제가 없다"),
    "D-unvalidated-remote": ("검증 없는 원격 입력", ("server.remote_validation",), "원격 입력 x 를 막는 형태의 typeof 검사로 거르지 않는다"),
    "D-url": ("URL 문자열", ("safety.url",), "resp.gate_open[Source] URL 이나 도메인 'roblox.co"),
    "D-vararg-handler": ("가변 인자 원격 처리", ("server.remote_validation",), "가변 인자(...)는 형식을 검사할 수 없다"),
    "D-variable-class-name": ("변수로 조립한 인스턴스 이름", ("safety.free_text",), "자유 입력 TextBox 를 만든다"),
    "D-variable-url": ("변수로 조립한 외부 링크", ("i18n.hardcoded_text", "safety.url"), "코드에 화면 문구 '://example.com' 가 있다"),
    "D-verdict-or-true": ("다른 조건과 섞인 판정", ("server.reward_after_verdict",), "원격 처리가 서버 판정(MissionService.coordinateMove ·"),
    "D-verdict-then-grant-outside": ("판정을 부르고 바깥에서 보상", ("server.reward_after_verdict",), "원격 처리가 서버 판정(MissionService.coordinateMove ·"),
    "D-wide-range": ("계약보다 넓은 범위 가드", ("server.remote_validation",), "원격 입력 x 의 범위 가드(-9999.0~9999.0)가 계약(-2~2)과 다"),
    "D-work-before-guard": ("받은 값을 담은 뒤에 하는 검증", ("server.remote_cooldown", "server.remote_validation"), "쿨다운 검사가 처리를 시작한 뒤에 있다"),
    "D-wrong-math": ("틀린 수학 대사", ("math.truth",), "claim.coordinate.label: 명제가 거짓이다 (E1)"),
    "D-wrong-type-guard": ("계약과 다른 종류로 한 검사", ("server.remote_validation",), "원격 입력 x 를 string 로 검사하지만 계약은 number 다"),
    "D-zero-width-banned": ("폭 0 문자를 끼운 금지어", ("safety.banned_terms",), "resp.gate_open[Source] 금지어 ['입국', '심사']"),
}
ITEM_IDS = {f"E{i}" for i in range(1, 7)} | {f"U{i}" for i in range(1, 15)}
MODES = {"static", "runtime", "human", "covered", "static_later"}


class TreeCase(unittest.TestCase):
    """깨끗한 트리를 임시 폴더에 복사해 고친 뒤 검사한다."""

    def make_tree(self, defect: str | None = None) -> Path:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        if defect:
            return run.build_defect(CLEAN, DEFECTS[defect], tmp)
        shutil.copytree(CLEAN, tmp, dirs_exist_ok=True)
        return tmp

    def edit(self, tree: Path, rel: str, old: str, new: str) -> None:
        path = tree / rel
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1, f"{rel}: '{old}' 가 한 번 있어야 한다")
        path.write_text(text.replace(old, new), encoding="utf-8")

    def add(self, tree: Path, rel: str, text: str) -> None:
        path = tree / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def failing(self, tree: Path) -> dict[str, list[str]]:
        return {k: v for k, v in run.run_checks(tree, MANIFEST, RULES).items() if v}

    def assertCaught(self, tree: Path, check_id: str, fragment: str = "") -> None:
        found = run.run_checks(tree, MANIFEST, RULES)[check_id]
        self.assertTrue(any(fragment in x for x in found), f"{check_id} 가 '{fragment}' 를 잡지 못함: {found}")


class PlantedDefectTest(TreeCase):
    """Q3-C1 — 깨끗한 데이터는 통과, 심은 결함은 정해진 검사가 정확히 잡는다."""

    def test_clean_fixture_passes_every_static_check(self):
        self.assertEqual(self.failing(self.make_tree()), {})

    def test_each_planted_defect_is_caught_by_exactly_its_checks(self):
        for defect in MANIFEST["defects"]:
            with self.subTest(defect=defect["id"]):
                self.assertEqual(sorted(self.failing(self.make_tree(defect["id"]))), sorted(defect["expected"]))

    def test_no_check_ever_crashes(self):
        """어떤 결함에서도 검사가 멈추지 않는다 — 멈춘 검사는 '잡았다'처럼 보이지만 이유가 없다 (리뷰 R-Q3 9차)."""
        for defect_id in sorted(EXPECTED_DEFECTS):
            with self.subTest(defect=defect_id):
                found = run.run_checks(self.make_tree(defect_id), MANIFEST, RULES)
                crashed = [f"{k}: {x}" for k, v in found.items() for x in v if "끝까지 돌지 못했다" in x]
                self.assertEqual(crashed, [])

    def test_required_defect_classes_are_planted(self):
        """기준 Q3-C1 이 이름으로 든 결함 종류마다 실제 고정 데이터가 있고, 그 데이터가 검사에 잡힌다."""
        by_class = {}
        for d in MANIFEST["defects"]:
            by_class.setdefault(d["class"], []).append(d)
        self.assertEqual(REQUIRED_CLASSES - set(by_class), set())
        for name in sorted(REQUIRED_CLASSES):
            with self.subTest(defect_class=name):
                for d in by_class[name]:
                    self.assertTrue(self.failing(self.make_tree(d["id"])))



    def test_defect_table_matches_the_independent_table(self):
        self.assertEqual({d["id"]: (d["class"], tuple(sorted(d["expected"]))) for d in MANIFEST["defects"]},
                         {i: (name, checks) for i, (name, checks, _frag) in EXPECTED_DEFECTS.items()})

    def test_each_defect_is_caught_by_the_listed_checks_with_the_intended_diagnosis(self):
        """결함마다 정해진 검사만 잡고, 그 이유(진단 문구)도 의도한 것이어야 한다 (리뷰 R-Q3 11차)."""
        for defect_id, (_name, expected, fragment) in sorted(EXPECTED_DEFECTS.items()):
            with self.subTest(defect=defect_id):
                found = self.failing(self.make_tree(defect_id))
                self.assertEqual(tuple(sorted(found)), expected)
                self.assertTrue(any(fragment in x for x in found[expected[0]]),
                                f"{defect_id}: '{fragment}' 가 진단에 없다 — {found[expected[0]][:2]}")

    def test_every_defect_class_is_named_in_the_criterion(self):
        """기준 Q3-C1 문장이 결함 종류를 하나도 빠짐없이 이름으로 든다 (리뷰 R-Q3 11차)."""
        statement = next(c["statement"] for n in GRAPH["nodes"] if n["id"] == "Q3" for c in n["criteria"] if c["id"] == "Q3-C1")
        self.assertEqual(sorted({name for name, _checks, _frag in EXPECTED_DEFECTS.values() if name not in statement}), [])

    def test_every_static_check_has_a_planted_defect(self):
        self.assertEqual(set(REGISTRY) - {c for d in MANIFEST["defects"] for c in d["expected"]}, set())

    def test_defect_edits_must_match_exactly_once(self):
        broken = copy.deepcopy(DEFECTS["D-banned-key" if "D-banned-key" in DEFECTS else "D-banned-term"])
        broken["edits"] = [{"file": "src/client/Hud.client.luau", "find": "없는 글자", "replace": "x"}]
        with self.assertRaises(ValueError):
            run.build_defect(CLEAN, broken, Path(tempfile.mkdtemp()))
        broken["edits"] = [{"file": "src/client/Hud.client.luau", "create": "x"}]
        with self.assertRaises(ValueError):
            run.build_defect(CLEAN, broken, Path(tempfile.mkdtemp()))


class MathClaimTest(TreeCase):
    """Q3-C2 — E1·E2 는 정확한 유리수 계산의 결정론 관문이다."""

    TRUE = [
        {"kind": "coordinate", "origin": [0, 0], "moves": [{"dir": "right", "n": 2}, {"dir": "up", "n": 1}], "states": [2, 1]},
        {"kind": "coordinate", "origin": [1, 1], "moves": [{"dir": "left", "n": 3}, {"dir": "down", "n": 2}], "states": [-2, -1]},
        {"kind": "slope", "rise": 1, "run": 3, "states": "1/3"},
        {"kind": "slope", "rise": 0, "run": 4, "states": 0},
        {"kind": "slope_compare", "this": {"rise": 3, "run": 1}, "other": {"rise": 1, "run": 1}, "states": "steeper"},
        {"kind": "slope_compare", "this": {"rise": 2, "run": 4}, "other": {"rise": 1, "run": 2}, "states": "equal"},
        {"kind": "slope_compare", "this": {"rise": -3, "run": 1}, "other": {"rise": 1, "run": 1}, "states": "steeper"},
        {"kind": "slope_compare", "this": {"rise": -1, "run": 2}, "other": {"rise": 1, "run": 1}, "states": "less_steep"},
        {"kind": "line_point", "line": {"m": 2, "b": 1}, "point": [2, 5], "states": True},
        {"kind": "line_point", "line": {"m": "1/2", "b": 0}, "point": [3, 1], "states": False},
    ]
    FALSE = [
        {"kind": "coordinate", "origin": [0, 0], "moves": [{"dir": "right", "n": 2}, {"dir": "up", "n": 1}], "states": [1, 2]},
        {"kind": "slope", "rise": 1, "run": 3, "states": "0.333"},       # 근삿값은 같지 않다 — 정확한 유리수
        {"kind": "slope_compare", "this": {"rise": 4, "run": 4}, "other": {"rise": 3, "run": 1}, "states": "steeper"},  # 큰 수가 더 가파른 게 아니다(K2 오개념)
        {"kind": "slope_compare", "this": {"rise": -3, "run": 1}, "other": {"rise": 1, "run": 1}, "states": "less_steep"},  # 내리막도 가파르다
        {"kind": "line_point", "line": {"m": 2, "b": 1}, "point": [2, 4], "states": True},
    ]
    ERRORS = [
        {"kind": "slope", "rise": 1, "run": 0, "states": 1},
        {"kind": "coordinate", "origin": [0, 0], "moves": [{"dir": "forward", "n": 1}], "states": [0, 1]},
        {"kind": "slope", "rise": 1.5, "run": 1, "states": 1},           # 실수는 근삿값이라 받지 않는다
        {"kind": "parabola", "states": 1},
        {"kind": "slope", "rise": "a", "run": 1, "states": 1},
        {"kind": "coordinate", "origin": [0], "moves": [], "states": [0, 0]},
        {"kind": "slope_compare", "this": {"rise": 1, "run": 1}, "other": {"rise": 1, "run": 1}, "states": "bigger"},
        {"kind": "line_point", "line": {"m": 1, "b": 0}, "point": [1, 1], "states": "yes"},
    ]

    def test_true_and_false_claims(self):
        for claim in self.TRUE:
            with self.subTest(claim=claim):
                self.assertIs(math_claims.evaluate(claim), True)
        for claim in self.FALSE:
            with self.subTest(claim=claim):
                self.assertIs(math_claims.evaluate(claim), False)

    def test_number_grammar(self):
        """정수·'분자/분모'·소수 글자는 정확한 유리수로 읽고, 실수(근삿값)와 수가 아닌 값은 거부한다."""
        for value, want in ((2, Fraction(2)), ("2", Fraction(2)), ("1/3", Fraction(1, 3)), ("0.5", Fraction(1, 2)), ("-3/4", Fraction(-3, 4))):
            with self.subTest(value=value):
                self.assertEqual(math_claims._num(value), want)
        for value in (0.5, 1.5, True, None, [1], "a", "1/0"):
            with self.subTest(value=value):
                with self.assertRaises(math_claims.ClaimError):
                    math_claims._num(value)
        self.assertIs(math_claims.evaluate({"kind": "slope", "rise": 1, "run": 2, "states": "0.5"}), True)
        self.assertIs(math_claims.evaluate({"kind": "slope", "rise": 1, "run": 3, "states": "0.333"}), False)

    def test_undecidable_claims_raise(self):
        for claim in self.ERRORS:
            with self.subTest(claim=claim):
                with self.assertRaises(math_claims.ClaimError):
                    math_claims.evaluate(claim)

    def test_deterministic(self):
        tree = self.make_tree("D-wrong-math")
        first = run.run_checks(tree, MANIFEST, RULES)["math.truth"]
        self.assertTrue(first)
        self.assertEqual([run.run_checks(tree, MANIFEST, RULES)["math.truth"] for _ in range(3)], [first] * 3)

    def test_line_must_state_each_part_of_the_claim(self):
        cases = [("출발 칸에서 오른쪽 2, 위 1 →", "출발 칸에서 오른쪽 3, 위 1 →", "오른쪽 2"),         # 이동 수가 다르다
                 ("옆으로 1칸 갈 때 2칸 올라가면 기울기는 2야.", "옆으로 1칸 갈 때 2칸 올라가면 가팔라져.", "기울기"),   # 용어가 없다
                 ("옆으로 1칸 갈 때 2칸 올라가면 기울기는 2야.", "옆으로 한 칸 갈 때 두 칸 올라가면 기울기는 2/3야.", "2")]                                        # 2 가 2/3 의 앞부분으로 걸리면 안 된다
        for old, new, fragment in cases:
            with self.subTest(fragment=fragment):
                tree = self.make_tree()
                self.edit(tree, "src/shared/Localization.csv", old, new)
                self.assertCaught(tree, "math.truth", f"'{fragment}' 을 말하지 않는다")

    def test_math_line_without_claim(self):
        self.assertCaught(self.make_tree("D-untied-math-line"), "math.truth", "명제가 없다")

    def test_claim_problems_inside_a_tree(self):
        cases = [("    rise: 2\n    run: 1\n", "    rise: 2\n    run: 0\n", "math.truth", "판정할 수 없다"),
                 ("    line_key: label.line.point\n", "    line_key: label.line.missing\n", "math.truth", "LocalizationTable 에 없다"),
                 ("claims:\n", "claims:\n  - just text\n", "math.conditions", "명제는 객체여야 한다")]
        for old, new, check, fragment in cases:
            with self.subTest(fragment=fragment):
                tree = self.make_tree()
                self.edit(tree, "content/math_claims.yaml", old, new)
                self.assertCaught(tree, check, fragment)

    def test_missing_and_inconsistent_conditions(self):
        cases = [("    conditions: {origin: [0, 0], axes: x_right_y_up}\n", "    conditions: {axes: x_right_y_up}\n", "조건 origin 가 빠졌다"),
                 ("    conditions: {origin: [0, 0], axes: x_right_y_up}\n", "    conditions: {origin: [1, 0], axes: x_right_y_up}\n", "기준점"),
                 ("    conditions: {origin: [0, 0], axes: x_right_y_up}\n", "    conditions: {origin: [0, 0], axes: x_right_y_down}\n", "축 방향"),
                 ("    conditions: {domain: real}\n", "    conditions: {domain: complex}\n", "정의역"),
                 ("    line: {m: 2, b: 1}\n    point: [2, 5]\n    states: true\n    states_text: 위에 있어\n    conditions: {domain: real}\n",
                  "    line: {m: '1/2', b: 1}\n    point: [2, 2]\n    states: true\n    states_text: 위에 있어\n    conditions: {domain: grid_integer}\n", "격자 정수"),
                 ("    this: {rise: 3, run: 1}\n", "    this: {rise: 3, run: 0}\n", "가로 변화가 0"),
                 ("    states_text: 더 가팔라\n    conditions: {run_nonzero: true, same_unit: grid_cell}\n",
                  "    states_text: 더 가팔라\n    conditions: {run_nonzero: true, same_unit: meter}\n", "단위"),
                 ("    kind: line_point\n", "    kind: circle\n", "명제 종류")]
        for old, new, fragment in cases:
            with self.subTest(fragment=fragment):
                tree = self.make_tree()
                self.edit(tree, "content/math_claims.yaml", old, new)
                self.assertCaught(tree, "math.conditions", fragment)

    def test_claims_required(self):
        tree = self.make_tree()
        (tree / "content" / "math_claims.yaml").unlink()
        self.assertCaught(tree, "math.truth", "수학 명제")


class RecordTest(TreeCase):
    """Q3-C3 — 검사마다 기록 하나(명령·결과·시각·대상 지문), 로컬 경로 없음."""

    def test_one_record_per_check_without_local_paths(self):
        tree = self.make_tree("D-banned-term")
        out = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out, True)
        results = run.run_checks(tree, MANIFEST, RULES)
        paths = run.write_records(tree, results, out, "harness/fixtures/clean")
        self.assertEqual(len(paths), len(MANIFEST["checks"]))
        self.assertEqual(sorted(p.stem for p in out.iterdir()), sorted(c["id"] for c in MANIFEST["checks"]))
        for p in paths:
            body = p.read_text(encoding="utf-8")
            for field in ("check:", "command: python3 -m harness.run", "result:", "time:", "target_sha256:", "findings:"):
                self.assertIn(field, body)
            recorded = re.search(r"target_sha256: ([0-9a-f]{64})\n", body)
            self.assertIsNotNone(recorded, f"대상 지문이 64자리 sha256 이 아니다: {p.name}")
            self.assertEqual(recorded.group(1), run.fingerprint(tree))
            self.assertNotIn(str(tree), body)
            self.assertNotIn(str(Path.home()), body)
        self.assertIn("result: FAIL", (out / "safety.banned_terms.txt").read_text(encoding="utf-8"))
        self.assertIn("result: PASS", (out / "safety.url.txt").read_text(encoding="utf-8"))

    def test_records_written_through_main_have_no_local_paths(self):
        tree, out = self.make_tree("D-url"), Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out, True)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run.main([str(tree), "--out", str(out)]), 1)
        for p in out.iterdir():
            body = p.read_text(encoding="utf-8")
            for secret in (str(tree), str(Path.home()), str(tree.parent)):
                self.assertNotIn(secret, body)

    def test_fingerprint_changes_with_content(self):
        tree = self.make_tree()
        before = run.fingerprint(tree)
        self.edit(tree, "src/client/Hud.client.luau", "sendCell(2, 1)", "sendCell(2, 2)")
        self.assertNotEqual(before, run.fingerprint(tree))

    def test_cli_exit_codes(self):
        out = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out, True)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run.main([str(self.make_tree()), "--out", str(out)]), 0)
            self.assertEqual(run.main([str(self.make_tree("D-url")), "--out", str(out)]), 1)
            self.assertEqual(run.main([str(out), "--out", str(out)]), 2)   # Rojo 프로젝트가 아님

    def test_broken_check_is_recorded_as_failure(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest["checks"].append({"id": "missing.check"})
        self.assertIn("구현이 없다", run.run_checks(self.make_tree(), manifest, RULES)["missing.check"][0])
        manifest = copy.deepcopy(MANIFEST)
        del manifest["config"]["reward_module"]
        self.assertIn("끝까지 돌지 못했다", run.run_checks(self.make_tree(), manifest, RULES)["server.reward_authority"][0])


class ManifestTest(unittest.TestCase):
    """Q3-C4 — 매니페스트가 E1~E6·U1~U14 와 안전 불변식을 빠짐없이, 방식·이유와 함께 담는다. 고정 데이터 지문이 맞다."""

    def test_items_cover_math_and_ui_lists(self):
        self.assertEqual(ITEM_IDS - {i["id"] for i in MANIFEST["items"]}, set())

    def test_every_item_has_a_reason(self):
        for item in MANIFEST["items"]:
            with self.subTest(item=item["id"]):
                self.assertTrue(item.get("reason", "").strip(), "항목마다 왜 그 방식·단계인지 적어야 한다")

    def test_each_item_has_mode_stage_and_reason_or_checks(self):
        q2 = {c["id"] for n in GRAPH["nodes"] if n["id"] == "Q2" for c in n["criteria"]}
        for item in MANIFEST["items"]:
            with self.subTest(item=item["id"]):
                self.assertIn(item["mode"], MODES)
                self.assertRegex(item["stage"], r"^Q[2-8]$")
                if item["mode"] == "static":
                    self.assertEqual(item["stage"], "Q3")
                    self.assertTrue(item["checks"])
                    self.assertEqual(set(item["checks"]) - set(REGISTRY), set())
                else:
                    self.assertTrue(item.get("reason", "").strip())
                if item["mode"] == "covered":
                    self.assertTrue(item["covered_by"])
                    self.assertEqual(set(item["covered_by"]) - q2, set())

    def test_safety_invariants_have_static_checks(self):
        static = {i["id"] for i in MANIFEST["items"] if i["mode"] == "static"}
        self.assertEqual({"INV-3", "INV-4", "INV-10", "INV-11", "INV-12", "INV-16"} - static, set())

    def test_registry_and_manifest_checks_match(self):
        self.assertEqual({c["id"] for c in MANIFEST["checks"]}, set(REGISTRY))
        self.assertEqual(set(REGISTRY) - {c for i in MANIFEST["items"] for c in i.get("checks", [])}, set())

    def test_width_budgets_fit_the_locked_glossary(self):
        """상한은 잠긴 Q2 용어집의 실측 폭보다 넓어야 한다 — 통과하는 원문을 거부하지 않는다."""
        for key, text in RULES.glossary["strings"].items():
            with self.subTest(key=key):
                self.assertLessEqual(i18n.width(text), i18n._budget(key, MANIFEST["config"]))

    def test_fixture_index_matches_files(self):
        index = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))["files"]
        self.assertEqual(index, run.fixture_index(FIXTURES))

    def test_fixture_index_detects_change(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
        (tmp / "clean" / "src" / "client" / "Hud.client.luau").write_text("-- 바뀜\n", encoding="utf-8")
        index = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))["files"]
        self.assertNotEqual(index, run.fixture_index(tmp))


class LuauTest(unittest.TestCase):
    """토크나이저 — 주석·문자열에 속지 않고 블록을 바로 센다."""

    SRC = '''
-- 주석 RewardService.grant("x")
--[==[ 긴 주석 https://example.com ]==]
local M = {}
local s = "a -- not comment"
local t = [[ long
string ]]
function M.grant(player: Player, rewardId: string, opts: {x: number}?)
  if not claimOnce(player, rewardId) then return end
  local v = if rewardId then 1 else 2
  for i = 1, 3 do
    while false do end
  end
  repeat local x = 1 until true
  if a then if b then c() end elseif d then e() else f() end
  local g = function(y) return y end
  return "hi"
end
return M
'''

    def test_comments_dropped_strings_kept(self):
        toks = luau.tokenize(self.SRC)
        self.assertEqual([t.text for t in toks if t.kind == luau.STRING], ["a -- not comment", " long\nstring ", "hi"])
        self.assertFalse(any(t.text == "RewardService" for t in toks))

    def test_function_bodies_and_typed_params(self):
        bodies = luau.function_bodies(luau.tokenize(self.SRC))
        self.assertEqual([b[0] for b in bodies], [["player", "rewardId", "opts"], ["y"]])
        self.assertEqual([t.text for t in bodies[0][1][-2:]], ["return", "hi"])

    def test_varargs_are_a_parameter(self):
        self.assertEqual(luau.function_bodies(luau.tokenize("function f(a, ...) end"))[0][0], ["a", "..."])

    def test_calls_exclude_definitions(self):
        toks = luau.tokenize("function M.grant(a) end\nM.grant(1, 2)\nx.M.grant(3)\n")
        self.assertEqual(len(luau.find_calls(toks, ("M", "grant"))), 1)
        self.assertEqual([[t.text for t in a] for a in luau.call_args(toks, luau.find_calls(toks, ("M", "grant"))[0])], [["1"], ["2"]])

    def test_syntax_errors(self):
        for src in ('local s = "unterminated', "local t = [[ open", "function f(a)\n  if a then\nend"):
            with self.subTest(src=src):
                with self.assertRaises(luau.LuauSyntaxError):
                    luau.function_bodies(luau.tokenize(src))


class CheckBranchTest(TreeCase):
    """검사 함수의 갈래마다 — 결함 데이터가 닿지 않는 경우를 변이로 본다."""

    def test_server_branches(self):
        cases = [
            ("src/server/RewardService.luau", "\tif not claimOnce(player, missionId .. \"|\" .. rewardId) then return end\n", "",
             "server.duplicate_reward", "중복 지급을 막지 않는다"),
            ("src/server/RewardService.luau", "function RewardService.grant(", "function RewardService.give(", "server.duplicate_reward", "grant 함수가 없다"),
            ("src/server/MissionService.luau", 'RewardService.grant(player, "reward.explorer_card", "m.gate_open")',
             'RewardService.grant(player, rewardName, "m.gate_open")', "server.duplicate_reward", "글자 그대로"),
            ("src/server/Main.server.luau", "SignalRemote.OnServerEvent:Connect(onSignal)", "SignalRemote.OnServerEvent:Connect(missingHandler)",
             "server.remote_validation", "처리 함수를 찾지 못했다"),
            ("src/server/Main.server.luau", "SignalRemote.OnServerEvent:Connect(onSignal)", "SignalRemote.OnServerEvent:Once(onSignal)",
             "server.remote_validation", "Connect(함수)·= 함수 가 아닌 방식"),
            ("src/server/Main.server.luau", '\tif typeof(x) ~= "number" or typeof(y) ~= "number" then return end\n',
             '\tif typeof(x) ~= "number" and typeof(y) ~= "number" then return end\n', "server.remote_validation", "막는 형태의 typeof"),
            ("src/server/Main.server.luau", '\tif typeof(x) ~= "number" or typeof(y) ~= "number" then return end\n',
             '\tassert(typeof(x) == "number" or typeof(y) == "number", "bad")\n', "server.remote_validation", "막는 형태의 typeof"),
            ("src/server/Main.server.luau", "local function onSignal(player: Player, x: unknown, y: unknown)\n"
             '\tif typeof(x) ~= "number" or typeof(y) ~= "number" then return end\n',
             "local function onSignal(player: Player, payload: unknown)\n\tif typeof(payload) ~= \"table\" then return end\n\tlocal x, y = payload.x, payload.y\n",
             "server.remote_validation", "표로 받은 payload.x"),
        ]
        for rel, old, new, check, fragment in cases:
            with self.subTest(fragment=fragment):
                tree = self.make_tree()
                self.edit(tree, rel, old, new)
                self.assertCaught(tree, check, fragment)

    def test_assert_counts_as_validation(self):
        tree = self.make_tree()
        self.edit(tree, "src/server/Main.server.luau", '\tif typeof(x) ~= "number" or typeof(y) ~= "number" then return end\n',
                  '\tassert(typeof(x) == "number" and typeof(y) == "number", "bad input")\n')
        self.assertEqual(run.run_checks(tree, MANIFEST, RULES)["server.remote_validation"], [])

    def test_bracket_access_is_normalized(self):
        toks = luau.normalize_index(luau.fold_strings(luau.tokenize('R["OnServer" .. "Event"]:Connect(f)\nlocal t = {["a"] = 1}\nm[key] = 2\n')))
        self.assertEqual([x.text for x in toks[:5]], ["R", ".", "OnServerEvent", ":", "Connect"])
        self.assertIn("[", [x.text for x in toks])        # 표 리터럴과 변수 색인은 그대로 둔다
        self.assertEqual(sum(1 for x in toks if x.text == "a"), 1)

    def test_module_alias_does_not_leak_across_statements(self):
        tree = source.load_tree(self.make_tree())
        tokens = next(f for f in tree.luau if f.rel.endswith("MissionService.luau")).tokens
        self.assertEqual(luau.require_aliases(tokens, "Analytics"), {"Analytics"})
        self.assertEqual(luau.require_aliases(tokens, "RewardService"), {"RewardService"})

    def test_table_payload_fields_need_type_and_range(self):
        tree = self.make_tree()
        self.edit(tree, "src/server/Main.server.luau",
                  'local function onSignal(player: Player, x: unknown, y: unknown)\n'
                  '\tif typeof(x) ~= "number" or typeof(y) ~= "number" then return end\n'
                  '\tif x < -GRID or x > GRID or y < -GRID or y > GRID then return end\n',
                  'local function onSignal(player: Player, payload: unknown)\n'
                  '\tif typeof(payload) ~= "table" then return end\n'
                  '\tif typeof(payload.x) ~= "number" or typeof(payload.y) ~= "number" then return end\n'
                  '\tlocal x, y = payload.x, payload.y\n')
        self.assertCaught(tree, "server.remote_validation", "표로 받은 payload.x 의 범위를 처리 전에")

    def test_reward_module_placement(self):
        tree = self.make_tree()
        shutil.move(tree / "src/server/RewardService.luau", tree / "src/shared/RewardService.luau")
        self.assertCaught(tree, "server.reward_authority", "클라이언트가 볼 수 있는 곳")
        tree = self.make_tree()
        (tree / "src/server/RewardService.luau").unlink()
        self.assertCaught(tree, "server.duplicate_reward", "보상 모듈 RewardService 이 없다")
        tree = self.make_tree()
        shutil.copy(tree / "src/server/Main.server.luau", tree / "src/shared/Remote.luau")
        self.assertCaught(tree, "server.remote_validation", "클라이언트가 볼 수 있는 코드")

    def test_i18n_branches(self):
        tree = self.make_tree()
        self.edit(tree, "src/client/Hud.client.luau", 'Text.get("goal.signal_2")', "Text.get(goalKey)")
        self.assertCaught(tree, "i18n.missing_key", "글자 그대로")
        tree = self.make_tree()
        self.edit(tree, "src/client/Hud.client.luau", 'goal.Text = Text.get("goal.signal_2")',
                  'goal.Text = game:GetService("LocalizationService"):GetTranslatorForPlayerAsync(nil):FormatByKey("goal.missing")')
        self.assertCaught(tree, "i18n.missing_key", "goal.missing")
        tree = self.make_tree()
        (tree / "src/shared/Localization.csv").unlink()
        self.assertCaught(tree, "i18n.missing_key", "LocalizationTable(CSV)이 없다")
        tree = self.make_tree()
        self.edit(tree, "src/client/Hud.client.luau", "sendCell(2, 1)", 'sendCell(2, 1)\nlocal label = "Open the gate"')
        self.assertCaught(tree, "i18n.hardcoded_text", "Open the gate")
        tree = self.make_tree()
        self.edit(tree, "src/shared/Localization.csv", "도시 언어 게이트가 열렸어!", "열렸어! 정말로. 진짜로. 와!")
        self.assertCaught(tree, "text.readability", "문장이 4개다")
        tree = self.make_tree()
        self.edit(tree, "src/shared/Localization.csv", "→ (2, 1). Ĉööŕðïñàţē.", "→ (2, 1) (3, 4). Ĉööŕðïñàţē.")
        self.assertCaught(tree, "i18n.do_not_translate", "번역 금지 조각이 원문과 다르다")

    def test_source_reading_problems_fail_every_check(self):
        cases = [("src/shared/Localization.csv", "Key,Source,Context,Example,qps-ploc", "Id,Text", "머리줄"),
                 ("src/server/Cooldown.luau", "return Cooldown\n", 'return "unterminated\n', "읽지 못했다"),
                 ("default.project.json", '"$path": "src/client"', '"$path": "src/missing"', "트리 안에 없다")]
        for rel, old, new, fragment in cases:
            with self.subTest(fragment=fragment):
                tree = self.make_tree()
                self.edit(tree, rel, old, new)
                results = run.run_checks(tree, MANIFEST, RULES)
                self.assertTrue(all(any(fragment in x for x in found) for found in results.values()), fragment)
        unmapped = "Rojo 프로젝트가 어디에도 넣지 않는 파일"
        tree = self.make_tree()
        self.add(tree, "src/stray/Loose.luau", "return {}\n")
        self.assertTrue(all(any(unmapped in x for x in v) for v in run.run_checks(tree, MANIFEST, RULES).values()))
        tree = self.make_tree()
        (tree / "default.project.json").write_text("{", encoding="utf-8")
        self.assertTrue(all(any("을 읽지 못했다" in x for x in v) for v in run.run_checks(tree, MANIFEST, RULES).values()))
        tree = self.make_tree()
        self.add(tree, "src/shared/Notes.toml", "a = 1\n")
        self.assertTrue(all(any("검사할 줄 모르는 파일" in x for x in v) for v in run.run_checks(tree, MANIFEST, RULES).values()))
        tree = self.make_tree()
        self.edit(tree, "src/shared/Localization.csv", "resp.gate_open,도시 언어 게이트가 열렸어!", "resp.gate_open,")
        self.assertTrue(all(any("원문(Source)이 비었다" in x for x in v) for v in run.run_checks(tree, MANIFEST, RULES).values()))

    def test_analytics_branches(self):
        base = '\tAnalytics.funnel(player, "gate_opened", {play_mode = "solo_npc"})'
        cases = [(base, '\tAnalytics.funnel(player, "gate_opened")', "꼴이어야 한다"),
                 (base, '\tAnalytics.funnel(player, "gate_opened", {mission = "m.gate_open"})', "필드 mission 는 허용되지 않는다"),
                 (base, '\tAnalytics.funnel(player, "gate_opened", fields)', "표 글자 그대로"),
                 (base, '\tAnalytics.funnel(player, "gate_opened", {"solo_npc"})', "이름 = 값 꼴"),
                 (base, '\tAnalytics.funnel(player, "gate_opened", {play_mode = "trio"})', "열거형 글자 그대로가 아니다")]
        for old, new, fragment in cases:
            with self.subTest(fragment=fragment):
                tree = self.make_tree()
                self.edit(tree, "src/server/MissionService.luau", old, new)
                self.assertCaught(tree, "analytics.calls", fragment)
        tree = self.make_tree()
        shutil.move(tree / "src/server/Analytics.luau", tree / "src/shared/Analytics.luau")
        self.assertCaught(tree, "analytics.calls", "분석 모듈이 클라이언트가 볼 수 있는 곳")
        tree = self.make_tree()
        self.edit(tree, "src/server/Analytics.luau", "AnalyticsService:LogOnboardingFunnelStepEvent(player, FUNNEL_STEPS[stepName], stepName, pack(fields))",
                  "AnalyticsService:LogCustomEvent(player, stepName, 1, pack(fields))")
        self.assertCaught(tree, "analytics.calls", "플랫폼 전송 함수 LogOnboardingFunnelStepEvent")

    def test_range_guard_needs_both_bounds_joined_by_or(self):
        tree = self.make_tree()
        self.edit(tree, "src/server/Main.server.luau", "\tif x < -GRID or x > GRID or y < -GRID or y > GRID then return end\n",
                  "\tif x < -GRID or x > GRID or y < -GRID or y > GRID or isBad(x) then return end\n")
        self.assertEqual(run.run_checks(tree, MANIFEST, RULES)["server.remote_validation"], [])
        tree = self.make_tree()
        self.edit(tree, "src/server/Main.server.luau", "\tif x < -GRID or x > GRID or y < -GRID or y > GRID then return end\n",
                  "\tif -GRID > x or GRID < x or -GRID > y or GRID < y then return end\n")
        self.assertEqual(run.run_checks(tree, MANIFEST, RULES)["server.remote_validation"], [])

    def test_absolute_rojo_path_is_refused_without_echoing_it(self):
        tree = self.make_tree("D-absolute-path")
        found = run.run_checks(tree, MANIFEST, RULES)["safety.url"]
        self.assertTrue(any("상대 경로여야 한다" in x for x in found), found)
        self.assertFalse(any("/tmp/gate-ui" in x for x in found), found)

    def test_guard_must_be_unconditional(self):
        tree = self.make_tree("D-nested-guard")
        self.assertCaught(tree, "server.remote_validation", "막는 형태의 typeof")

    def test_reward_helper_kinds(self):
        self.assertCaught(self.make_tree("D-anonymous-reward-helper"), "server.reward_after_verdict", "서버 판정")
        self.assertCaught(self.make_tree("D-else-reward"), "server.reward_after_verdict", "서버 판정")

    def test_analytics_module_is_not_trusted(self):
        self.assertCaught(self.make_tree("D-analytics-module-literal"), "analytics.calls", "정해진 값")
        self.assertCaught(self.make_tree("D-analytics-module-pii"), "analytics.calls", "개인정보 속성 Name")

    def test_unresolved_ui_assembly_has_its_own_diagnosis(self):
        found = run.run_checks(self.make_tree("D-unresolved-ui-text"), MANIFEST, RULES)["i18n.hardcoded_text"]
        self.assertTrue(any("문구 키 호출이 아닌 함수" in x for x in found), found)

    def test_rojo_mapping_must_stay_in_src(self):
        tree = self.make_tree("D-mapped-outside-src")
        self.assertTrue(all(any("소스 폴더" in x for x in v) for v in run.run_checks(tree, MANIFEST, RULES).values()))

    def test_interpolated_strings_are_refused(self):
        tree = self.make_tree("D-interpolated-string")
        self.assertTrue(all(any("보간 문자열" in x for x in v) for v in run.run_checks(tree, MANIFEST, RULES).values()))

    def test_broken_project_structure_still_records(self):
        tree = self.make_tree("D-project-tree-not-object")
        results = run.run_checks(tree, MANIFEST, RULES)
        self.assertEqual(len(results), len(MANIFEST["checks"]))
        self.assertTrue(all(any("tree 는 객체여야" in x for x in v) for v in results.values()))

    def test_unresolved_module_members_are_refused(self):
        """모듈의 멤버를 값으로 고르면 풀어서 보고, 끝내 풀리지 않으면 거부한다 — 검사기가 읽을 수 있는 코드만 쓴다."""
        for defect, check in (("D-dynamic-reward-member", "server.duplicate_reward"),
                              ("D-dynamic-text-member-unresolved", "i18n.missing_key"),
                              ("D-dynamic-analytics-member", "analytics.calls")):
            with self.subTest(defect=defect):
                self.assertCaught(self.make_tree(defect), check, "값을 알 수 없는")

    def test_guard_order_and_claim_once(self):
        self.assertCaught(self.make_tree("D-range-before-type"), "server.remote_validation", "범위 검사보다 뒤에")
        self.assertCaught(self.make_tree("D-claimonce-not-called"), "server.duplicate_reward", "실제 호출이어야")

    def test_indirect_reward_path_needs_a_verdict(self):
        """간접 도우미를 거쳐도 보상은 서버 판정 뒤에만 — 스스로 판정하는 함수를 부르는 것은 괜찮다."""
        self.assertCaught(self.make_tree("D-indirect-reward-helper"), "server.reward_after_verdict", "서버 판정")
        self.assertEqual(run.run_checks(self.make_tree(), MANIFEST, RULES)["server.reward_after_verdict"], [])

    def test_dynamic_members_are_resolved_or_refused(self):
        self.assertCaught(self.make_tree("D-dynamic-remote-member"), "server.remote_validation", "막는 형태의 typeof")
        self.assertCaught(self.make_tree("D-unknown-remote-member"), "server.remote_validation", "값을 알 수 없는 멤버")
        self.assertCaught(self.make_tree("D-dynamic-text-member"), "i18n.missing_key", "goal.missing")

    def test_records_do_not_keep_stale_files(self):
        """지난 실행의 기록이 남아 검사 수와 기록 수가 어긋나지 않는다 (리뷰 R-Q3 11차)."""
        tree, out = self.make_tree(), Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out, True)
        (out / "old.check.txt").write_text("지난 실행", encoding="utf-8")
        results = run.run_checks(tree, MANIFEST, RULES)
        run.write_records(tree, results, out, "harness/fixtures/clean")
        self.assertEqual(sorted(p.stem for p in out.glob("*.txt")), sorted(results))

    def test_values_moved_through_variables_are_resolved(self):
        """값을 변수로 한 단계 더 돌려도 잡는다 — 그리고 끝까지 풀리지 않으면 거부한다."""
        for defect, check in (("D-variable-class-name", "safety.free_text"), ("D-variable-url", "safety.url"),
                              ("D-two-step-grant-alias", "server.duplicate_reward"), ("D-text-alias-chain", "i18n.missing_key"),
                              ("D-player-alias-pii", "analytics.calls"), ("D-analytics-dot-call", "analytics.calls")):
            with self.subTest(defect=defect):
                self.assertTrue(run.run_checks(self.make_tree(defect), MANIFEST, RULES)[check])
        tree = self.make_tree()
        self.edit(tree, "src/client/Hud.client.luau", "sendCell(2, 1)", 'sendCell(2, 1)\nlocal c = Instance.new(className)')
        self.assertCaught(tree, "safety.free_text", "글자 그대로 알 수 없다")

    def test_decision_values_must_be_known_or_refused(self):
        """값을 쓰는 판단 지점마다 — 글자 그대로이거나 풀리는 값이어야 하고, 아니면 거부한다 (전수 점검, 리뷰 R-Q3 10차)."""
        for defect, check, fragment in (("D-analytics-computed-event", "analytics.calls", "이벤트 이름 자리에"),
                                        ("D-ui-text-from-function", "i18n.hardcoded_text", "문구 키 호출이 아닌 함수"),
                                        ("D-player-alias-dynamic-authority", "server.reward_authority", "값을 알 수 없는 방식"),
                                        ("D-reassigned-grid-after-block", "server.remote_validation", "범위")):
            with self.subTest(defect=defect):
                self.assertCaught(self.make_tree(defect), check, fragment)

    def test_constant_table_lookup_is_not_refused(self):
        """받은 값으로 상수 표를 조회하는 정상 코드는 막지 않는다."""
        self.assertEqual(run.run_checks(self.make_tree(), MANIFEST, RULES)["analytics.calls"], [])

    def test_ordinary_string_building_is_not_refused(self):
        """키를 만드는 평범한 문자열 조립은 막지 않는다 — URL 조각이 섞였을 때만 거부한다."""
        tree = self.make_tree()
        self.edit(tree, "src/client/Hud.client.luau", "sendCell(2, 1)", 'sendCell(2, 1)\nlocal key = "goal." .. tostring(1)')
        self.assertEqual(run.run_checks(tree, MANIFEST, RULES)["safety.url"], [])

    def test_remote_contract_rules(self):
        self.assertCaught(self.make_tree("D-wrong-type-guard"), "server.remote_validation", "계약은 number 다")
        self.assertCaught(self.make_tree("D-wide-range"), "server.remote_validation", "계약(-2~2)과 다르다")
        self.assertCaught(self.make_tree("D-contract-off-canonical"), "server.remote_validation", "정본 값")
        self.assertCaught(self.make_tree("D-missing-contract"), "server.remote_validation", "입력 계약이")
        tree = self.make_tree()
        (tree / "content" / "remote_contracts.yaml").unlink()
        self.assertTrue(all(any("remote_contracts.yaml 이 없다" in x for x in v) for v in run.run_checks(tree, MANIFEST, RULES).values()))

    def test_cooldown_must_be_the_only_condition(self):
        self.assertCaught(self.make_tree("D-cooldown-with-extra-condition"), "server.remote_cooldown", "멈추지 않는다")

    def test_verdict_polarity_and_aliases(self):
        self.assertCaught(self.make_tree("D-equals-false-verdict"), "server.reward_after_verdict", "서버 판정")
        self.assertCaught(self.make_tree("D-alias-grant-in-handler"), "server.reward_after_verdict", "서버 판정")

    def test_claim_needing_states_text_must_have_it(self):
        tree = self.make_tree()
        self.edit(tree, "content/math_claims.yaml", "    rise: 2\n    run: 1\n    states: 2\n", "    rise: 1\n    run: 2\n    states: '1/2'\n")
        self.assertCaught(tree, "math.truth", "states_text")

    def test_states_text_must_appear_in_the_line(self):
        tree = self.make_tree()
        self.edit(tree, "content/math_claims.yaml", "    states_text: 더 가팔라\n", "    states_text: 덜 가팔라\n")
        self.assertCaught(tree, "math.truth", "'덜 가팔라' 을 말하지 않는다")

    def test_safety_branches(self):
        tree = self.make_tree()
        rules = source.Rules(RULES.events, {**RULES.glossary, "banned_terms": []}, RULES.world_spec, RULES.canonical)
        self.assertIn("금지어 목록을 읽지 못했다", run.run_checks(tree, MANIFEST, rules)["safety.banned_terms"][0])
        tree = self.make_tree()
        self.edit(tree, "src/server/Cooldown.luau", "local last: {[string]: number} = {}",
                  "local last: {[string]: number} = {}\nlocal roll = math.random\n")
        self.assertCaught(tree, "safety.random_or_paid_reward", "다른 이름(roll)에 담았다")
        tree = self.make_tree()
        self.edit(tree, "src/client/Hud.client.luau", "sendCell(2, 1)", 'sendCell(2, 1)\nlocal link = "see www.example.org"')
        self.assertCaught(tree, "safety.url", "www.")

    def test_random_allowed_module_is_an_explicit_exception(self):
        manifest = copy.deepcopy(MANIFEST)
        tree = run.build_defect(CLEAN, DEFECTS["D-random-helper"], Path(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, tree, True)
        self.assertTrue(run.run_checks(tree, manifest, RULES)["safety.random_or_paid_reward"])
        manifest["config"]["random_allowed_modules"] = ["Chance"]
        self.assertEqual(run.run_checks(tree, manifest, RULES)["safety.random_or_paid_reward"], [])


if __name__ == "__main__":
    unittest.main()
