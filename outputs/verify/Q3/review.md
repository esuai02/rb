critical | harness/checks/server.py:387-407 | 거짓 판정 가지의 보상을 허용한다 | `_inside_verdict`가 `else` 범위를 구분하지 않아 `if coordinateMove(...) then ... else openGate() end`도 유효 판정으로 본다 | CFG로 then/else 범위를 분리하고 false branch·`== false` 변이를 추가한다

critical | harness/checks/server.py:35-45,369-384 | 익명 보상 헬퍼를 통한 판정 우회가 가능하다 | `reward_reaching`은 이름 있는 함수만 기록하므로 `local award = function() RewardService.grant(...) end` 호출을 `reward_after_verdict`가 추적하지 않는다 | 익명 함수·테이블 함수 할당까지 호출 그래프를 추적한다

major | harness/checks/server.py:169-238,279-345 | 원격 입력 가드의 실행 경로를 검증하지 않는다 | 중첩된 특정 조건 안의 `typeof`·범위 검사를 전체 핸들러의 선행 검증으로 인정해 다른 경로의 미검증 입력을 통과시킨다 | 지배 관계를 계산해 모든 입력 사용 경로를 차단하는지 검사한다

major | harness/checks/server.py:73-83 | INV-4의 경험치·자격·시민권 권한을 검사하지 않는다 | `authority_names`와 검사 대상이 DataStore·leaderstats·OwnedRewards 등에 한정되고 `Experience`·`Eligibility`·`Citizenship`이 없다 | INV-4의 모든 권한 경로를 폐쇄 목록으로 추가하고 서버 모듈 밖 변이를 심는다

major | harness/checks/analytics.py:53-59 | 분석 모듈 내부의 개인정보·허용 목록 우회를 신뢰한다 | 모듈 파일은 플랫폼 API 이름이 토큰에 존재하기만 하면 `continue`하므로 `player.Name` 또는 임의 이벤트를 실제 전송해도 통과한다 | 모듈 구현도 이벤트·필드·값 검사를 적용하거나 원시 전송 API를 모듈 밖에서 사용할 수 없게 한다

major | harness/checks/i18n.py:33-43 | 함수 별칭을 통한 끊긴 번역 키를 놓친다 | `local get = Text.get; get("missing")`은 `_key_calls`가 추적하지 않고 `"missing"`은 식별자라 하드코딩 검사도 통과한다 | `Text.get`·번역기 메서드의 함수 별칭을 추적하거나 별칭 사용을 거부한다

major | harness/source.py:131-151 | `src` 밖의 Rojo 매핑 자체를 검사하지 않는다 | 임의 상대 경로를 그대로 `owners`에 등록한다. 현재 D-mapped-outside-src는 경로가 아니라 그 안의 `TextBox` 때문에 잡힌다 | Rojo 매핑 경로가 허용된 `src/**`인지 별도 검사하고 경로 변이를 추가한다

major | tests/test_harness.py:72-93 | C1의 “60종” 완전성을 독립적으로 검증하지 않는다 | 테스트가 결함 목록과 기대 검사를 모두 `manifest.json`에서 읽으며, `REQUIRED_CLASSES`도 19개만 고정한다. 비핵심 결함을 매니페스트에서 삭제해도 통과할 수 있다 | 테스트에 독립적인 60개 결함 ID·분류 집합을 두고 정확히 일치하는지 검증한다
