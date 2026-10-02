major | tools/validate_graph.py:75,441 | role.contribution이 임의 문자열이어도 Q1 행동 참조로 검증되지 않는다 | Graph의 ping_anchor_cell을 does_not_exist로 바꿔도 전체 검사가 PASS | contribution을 Q1 action key 또는 별도 폐쇄 열거형으로 제한하고 변이 테스트 추가

major | tools/validate_graph.py:788-795 | 목표 표현이 일상 표현의 일부 단어만 포함해도 통과한다 | answer.coordinate.signal_cell을 오른쪽으로 바꾸고 이름표도 맞춰도 전체 검사가 PASS | 목표 표현의 필수 구성요소·월드 결과 연결을 구조화해 검증하고 부분 표현 변이 추가

major | tools/validate_graph.py:901-906 | 시나리오가 실제 재도전·멈춤·일상어 사용을 검증하지 않고 variation 문자열만 검사한다 | 시나리오의 기대 이벤트를 임의 축소해도 variation/path 조건만 만족하면 PASS; 실제 입력·표현 사용 필드가 없음 | 시나리오에 검증 가능한 행동·표현·시도·정지 상태를 추가하고 의미 변이 테스트

minor | tools/validate_graph.py:518,143-147 | 모든 검사 줄에 대응하는 변이 테스트가 없다 | max_custom_events와 coop_sync_window·server_cooldown·label/hint 범위 변이가 tests/test_q2_graph.py에 없음 | 각 분기·범위 항목별 실패 변이 테스트 추가
