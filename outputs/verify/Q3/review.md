major | harness/checks/math_claims.py:30-36; tests/test_harness.py:276-299 | Q3-C2의 수치 문법과 테스트가 불일치한다 | `Fraction("0.333")`은 333/1000으로 허용되어 `evaluate()`가 False를 반환하지만, 테스트는 ClaimError를 기대한다. 제시된 C2 PASS 증거와 현재 코드는 양립하지 않는다 | `_num()`을 정수 또는 `분자/분모`만 허용하도록 고치거나 테스트·기준을 일치시킨다

major | harness/checks/server.py:86-103,119-148,543-559 | 클라이언트의 직접 `RewardService.grant()` 호출이 검출되지 않는다 | 클라이언트 파일의 고유 보상 호출은 `reward_authority=[]`, `duplicate_reward=[]`, `reward_after_verdict=[]`가 된다. 권한 검사는 설정된 저장 권한 이름만 보고, 보상 호출의 클라이언트 여부를 보지 않는다 | `grant_calls()`가 `client_visible` 파일에서 발견되면 즉시 거부한다

major | harness/checks/i18n.py:106-158,161-173 | 해석 불가능한 대괄호 UI 속성이 화면 문구 검사를 우회한다 | `goal[prop] = makeText()`에서 `prop`이 해석되지 않으면 `_ui_assignments()`가 찾지 않고, 하드코딩 검사도 함수 결과를 잡지 못한다 | 대괄호 대입도 수집하고 속성 또는 RHS가 해석되지 않으면 거부한다

minor | tests/test_harness.py:356-371; harness/run.py:100-106 | Q3-C3 테스트가 기록된 대상 지문이 실제 지문인지 검증하지 않는다 | 테스트는 `target_sha256:` 존재만 확인하며 `run.fingerprint(tree)`와의 일치를 확인하지 않는다 | 각 기록의 지문을 계산값 및 64자리 SHA-256 형식과 비교한다

minor | harness/checks/math_claims.py:221-235; harness/run.py:77-81 | YAML은 유효하지만 `conditions`가 스칼라면 수학 검사가 중단된다 | `conditions: 1`에서 `c not in cond`가 TypeError를 내고 실행기가 일반적인 “검사가 끝까지 돌지 못했다”로 처리한다 | `conditions`가 dict인지 먼저 검사하고 명시적 진단을 반환한다
