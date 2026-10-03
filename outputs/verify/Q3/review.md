major | harness/checks/i18n.py:108-240 | 괄호로 감싼 UI 하드코딩 문구를 검출하지 못한다 | `goal.Text = ("Ready")`가 모든 검사에서 통과한다. 괄호 안 문자열은 `_ui_text_literals`의 depth 조건과 `unresolved_ui_text`의 문자열 존재 조건을 모두 우회한다 | UI 대입 RHS의 모든 문자열 리터럴을 검사하고, 허용된 단일 문구 키 호출만 예외 처리

major | harness/checks/server.py:171-186 | `claimOnce`가 실제로 중복을 막는지 검증하지 않는다 | `claimed[slot] = false`로 바꿔도 읽기·쓰기·false 반환·동일 키 조건만 충족해 통과하며, 호출마다 `true`를 반환해 중복 지급된다 | 기록 대입값이 `true`인지와 읽기→거부→표시 순서를 구조적으로 검증

major | harness/checks/math_claims.py:207-212, 143-146 | 비문자열 `line_text`·`states_text`가 존재하는 것처럼 처리되어 분수 명제와 대사의 연결을 우회한다 | `m=1/3,b=13/3, point=[2,5], line_text=123`인 참 명제가 실제 식 대사 없이 통과한다. 존재 검사는 `str(...)`로 하지만 패턴 추가는 문자열 타입만 허용한다 | 두 필드를 실제 문자열로 엄격히 검증하고, 문자열이 아니면 실패시키며 반드시 대사에 일치시킬 것
