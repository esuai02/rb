major | harness/checks/math_claims.py:189 | 숫자만 있는 수학 대사는 명제가 없어도 통과한다 | `has_math`가 등록 용어 또는 `do_not_translate` 조각이 있을 때만 검사한다. 예: `2 + 2 = 4`는 `math.truth`에서 무검출 | 수학식·수치 패턴을 확장하고 명제 연결 회귀 테스트 추가
major | harness/checks/server.py:341 | 입력을 변수 계산·대입으로 사용한 뒤 타입·범위 검사를 해도 통과한다 | `_first_work`가 호출·멤버호출만 작업으로 세므로 `local z = x + y` 뒤 가드가 검출되지 않음 | 데이터 의존 읽기·대입·속성 쓰기도 첫 작업으로 추적
major | harness/checks/server.py:276 | `<=`·`>=` 범위가 `<`·`>`와 같은 것으로 판정된다 | `_comparisons`가 비교 연산자를 방향만으로 축약해 경계값을 잘못 거부하는 가드도 계약 범위와 같다고 통과시킴 | 연산자 포함 여부까지 보존해 허용 구간을 검증
major | harness/checks/server.py:508 | 판정식에 `or true`·`and true`가 섞여도 참 판정 뒤 보상으로 인정한다 | `_inside_verdict`가 판정 호출 존재와 단순 부정 여부만 확인함 | 판정식의 논리식을 분석해 보상이 실제 참 결과에만 도달하는지 검증
major | harness/checks/server.py:19 | 보상 함수 별칭을 두 단계 이상 넘기면 중복·무판정 보상이 통과한다 | `_grant_aliases`는 `local g = RewardService.grant` 한 단계만 추적하고 `local h = g; h(...)`는 누락 | 별칭을 고정점까지 전파하거나 해석 불가 호출을 실패 처리
major | harness/checks/analytics.py:94 | 분석 모듈이 점 표기 API로 임의의 이벤트 문자열을 보내도 통과한다 | 플랫폼 호출 탐지가 `find_calls`에서 `:`만 보조 처리하고 `AnalyticsService.LogCustomEvent(...)`의 `.` 호출은 검사하지 않음 | 점·콜론 양쪽 호출 형태를 동일하게 검사
major | harness/checks/analytics.py:100 | 플레이어 별칭을 통한 개인정보 필드가 통과한다 | `p = player; fields.who = p.Name`에서 개인정보 검사는 수신자 이름을 `player/plr/target/user`로 제한함 | 플레이어 별칭의 데이터 흐름을 추적하거나 별칭 속성 접근을 금지
major | harness/checks/i18n.py:39 | 문구 함수 별칭을 재별칭하면 끊긴 키가 통과한다 | `Text.get → get` 한 단계만 수집하며 `use = get; use("missing")`는 `_key_calls`에 없음 | 함수 별칭을 전이적으로 추적하거나 UI 문구 호출의 미해석 키를 실패 처리
major | harness/checks/i18n.py:140 | 함수가 반환한 식별자형 하드코딩 문구가 UI에 들어가도 통과한다 | `label() -> "Open"; goal.Text = label()`은 UI RHS에 문자열 토큰이 없고 `"Open"`은 `IDENTIFIER`로 제외됨 | 문자열 반환 함수와 UI 대입을 연결하거나 미해석 UI 문자열을 보수적으로 실패 처리
major | harness/checks/safety.py:49 | 변수로 쪼갠 `TextBox` 생성이 자유 입력 검사에서 빠진다 | `a = "Text"; b = "Box"; Instance.new(a .. b)`는 `fold_strings` 대상이 아니며 토큰에 `TextBox`가 없음 | 상수 전파를 추가하거나 동적 `Instance.new` 클래스명을 실패 처리
major | harness/checks/safety.py:34 | URL을 변수 조각으로 조합하면 외부 링크 검사를 우회한다 | URL 정규식은 각 문자열 토큰을 따로 검사하므로 `"https" .. "://example" .. ".com"`을 탐지하지 못함 | 상수 문자열 전파 후 전체 식을 검사하고 미해석 URL 조각도 차단
major | harness/source.py:144 | 같은 소스 파일을 서버·클라이언트 양쪽에 매핑해도 클라이언트 노출이 누락된다 | `owners.setdefault`가 첫 매핑만 보존해 후속 client-visible 매핑을 무시함 | 다중 소유 매핑을 오류로 기록하고 모든 매핑의 노출성을 검증
