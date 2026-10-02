major | harness/checks/server.py:489-496 | 뒤집힌 쿨다운 조건을 통과시킨다 | `if not not Cooldown.allow(...)`와 `if not Cooldown.allow(...) == false`도 sole guard로 인정된다 | 조건을 정확히 `not <단일 호출>`로 파싱하고 추가 토큰을 거부

major | harness/checks/server.py:331-355 | 재할당된 범위 상수를 정본 경계로 오인한다 | `GRID = 2` 뒤 `GRID = 999`가 있어도 최초 값으로 범위를 통과시킬 수 있다 | 재할당 상수는 미해결로 처리하거나 리터럴·불변 정본만 허용

major | harness/checks/server.py:88-97 | 동적 멤버를 통한 보상 권한 우회를 잡지 못한다 | `player[pickField()].Value += 1`에는 `authority_names` 토큰이 없어 클라이언트에서도 무검출이다 | 권한 객체의 미해결 대괄호·동적 서비스/멤버 접근은 fail-closed

major | harness/checks/math_claims.py:191-196 | 숫자 없는 수학 대사를 명제 없는 대사로 검출하지 못한다 | 숫자와 함께 있을 때만 `has_math`가 참이므로 `기울기가 더 가팔라.`가 통과한다 | 잠긴 수학 용어·수학 대사 키를 숫자 조건 없이 명제와 연결

major | harness/checks/math_claims.py:81-85,129-136 | 분수 계수의 line-point 명제가 대사에 계수를 포함하지 않아도 통과한다 | 분수에는 `_number_re`가 `None`을 반환하고, `states_text`와 점만 있으면 통과한다 | 분수 계수마다 데이터가 제공한 정규화 표현 패턴을 필수로 검사

major | harness/luau.py:58-73 | 백틱 보간식 내부의 서버·안전 코드를 검사하지 않는다 | `{player}`를 포함한 백틱을 통째로 STRING 토큰으로 만들며, 테스트도 이를 전제한다(tests/test_harness.py:442) | 백틱 보간식을 코드 토큰으로 재귀 파싱하거나 보간식 백틱을 거부

major | harness/source.py:122-129, harness/run.py:66-71 | 잘못된 JSON 구조에서 실행기가 중단되어 Q3-C3 기록을 남기지 못한다 | `tree: []`는 `_mappings(...).items()`의 `AttributeError`를 발생시키고 `run_checks`가 포착하지 않는다 | 프로젝트 구조를 사전 검증하고 해당 예외를 `Tree.problems`로 변환해 모든 검사 기록을 생성
