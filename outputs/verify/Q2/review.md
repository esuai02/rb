major | tools/validate_graph.py:53-70,256-287,292-298 | Q2-C1의 닫힌 형식이 실제로 닫히지 않았다. `S`가 문자열뿐 아니라 수·불리언·null을 허용하고 `graph.id`는 의미 검사를 하지 않는다. `graph.id=False` 또는 `"garbage"` 변이는 전체 검사에서 통과하며, 잘못된 수치형은 검사기를 충돌시킨다. | 문자열·nullable 문자열 등 타입을 분리하고 모든 필드 타입을 검사하며 해당 변이 테스트를 추가한다.

major | tools/validate_graph.py:520-562 | Q2-C4가 근거 필드의 형식을 검사하지 않는다. `cv.gate_name.rationale=2` 및 `measure_at=1` 변이가 통과한다. 숫자를 근거로 인정해 “근거” 합격 기준을 우회할 수 있다. | 정본 항목 전체 스키마를 검사해 rationale·refs·measure_at·q1_paths를 올바른 문자열/목록/사전으로 제한한다.

major | tools/validate_graph.py:41-43,617-630; specs/localization/terms/ko-KR.yaml:127-158 | Q2-C5 금지어 하한이 불완전하다. `nationality`가 목록에 없어 해당 단어를 문구에 넣어도 통과하며, `친구를 초대해 보상을 받아!`도 `초대하면`의 정확한 형태가 아니어서 통과한다. | 한·영 국적/신분 금지어와 보상형 초대의 형태·조합 패턴을 명시하고 변이 테스트를 추가한다.

major | tools/validate_graph.py:674-687; tests/test_q2_graph.py:571-585 | Q2-C7이 협동 보상의 수령 대상을 검사하지 않는다. `reward.coop_trail.basis=role_contribution`인 상태에서 `granted_to=all_finishers`로 바꿔도 통과해 INV-4의 역할별 기여 기준을 우회한다. | `role_contribution`이면 `granted_to=contributing_players`를 강제하고 변이 테스트를 추가한다.
