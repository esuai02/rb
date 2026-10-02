major | harness/checks/server.py:227 | 원격 입력을 사용한 뒤에 `typeof` 가드가 있어도 통과한다 | `_guards`가 가드의 존재만 검사하며 순서를 보지 않는다. `coordinateMove(...x,y)` 후 가드하는 메모리 반례가 `[]`를 반환했다 | 입력 사용보다 앞선 가드만 인정하고 회귀 테스트 추가
major | harness/checks/server.py:215 | INV-4의 범위·상태 검증을 검사하지 않고 타입만 검사한다 | 구현과 테스트가 `typeof` 검사만 요구하며 범위·상태 조건이 없다 | 원격 입력별 범위·상태 규칙을 추가하고 위반 fixture 추가
major | harness/checks/server.py:238 | 쿨다운 호출이 처리 뒤에 있거나 반환값을 무시해도 통과한다 | `remote_cooldown`은 `Cooldown.allow` 호출 존재만 검사하며 메모리 반례가 `[]`를 반환했다 | 업무 처리 전에 실패 반환을 강제하는 구조 검증 추가
major | harness/checks/server.py:90 | 보상·저장 권한 이름을 문자열 결합으로 우회할 수 있다 | `player["leader" .. "stats"]` 반례가 `reward_authority`에서 검출되지 않았다 | 상수식 결합을 평가하거나 권한 접근 AST/데이터흐름 검사를 추가
major | harness/checks/safety.py:43 | `TextBox`를 문자열 결합으로 생성하면 자유 입력 검사를 우회한다 | `Instance.new("Text" .. "Box")` 반례가 `safety.free_text`에서 검출되지 않았다 | `Instance.new`의 상수 문자열을 정규화해 클래스명을 검사
major | harness/checks/safety.py:31 | URL을 문자열 조각으로 결합하면 외부 링크 검사를 우회한다 | `"https" .. "://" .. "example" .. ".com"` 반례가 `safety.url`에서 검출되지 않았다 | 상수 문자열 결합을 접어 URL 검사하고 회귀 fixture 추가
major | harness/checks/safety.py:14 | zero-width 문자를 삽입한 금지어를 통과시킨다 | `입\u200b국`이 `_squash` 후에도 금지어로 검출되지 않았다 | Unicode 정규화와 `Cf` 문자 제거 후 금지어 검사
major | harness/checks/i18n.py:129 | 대괄호 UI 속성과 식별자형 문구를 하드코딩 검사에서 누락한다 | `goal["Text"] = "Ready"` 반례가 `i18n.hardcoded_text`에서 `[]`를 반환했다 | `obj["Text"]`를 검사하고 UI 대입 문맥의 식별자형 문자열도 문구로 판정
major | harness/source.py:130 | 절대 Rojo 경로가 검사 기록에 노출될 수 있다 | `tree.problems`의 원시 `$path`가 `run.py:80-91`에서 그대로 기록된다. 절대 `$path`를 거부해도 오류 메시지에 경로가 남는다 | 기록 전 경로를 기준명으로 치환하고 절대 경로 fixture 추가
major | tests/test_harness.py:28 | Q3-C1의 모든 결함 유형을 테스트한다고 볼 수 없다 | `REQUIRED_CLASSES`가 `검증 없는 RemoteFunction`, `클라이언트 분석 전송`, `번역된 수식` 등 기준 명시 유형을 포함하지 않는다. 해당 fixture를 삭제해도 다른 결함으로 검사 집합 테스트가 통과할 수 있다 | 기준의 모든 결함 유형을 명시하고 유형별 fixture 존재를 단정
minor | tests/test_harness.py:249 | Q3-C4의 “항목마다 이유”를 검사하지 않는다 | 정적 E1·E2·E5 및 INV 항목 6개에 `reason`이 없지만 정적 항목은 `checks`만 있으면 통과한다 | 모든 항목에 비어 있지 않은 `reason`을 요구하고 매니페스트에 추가
