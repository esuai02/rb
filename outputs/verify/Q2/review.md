major | tools/validate_graph.py:32-33,526-529 | 복합 개인정보 이벤트명(`student_fullname_logged`, `child_nickname`)이 금지 토큰 분할 방식 때문에 통과한다(INV-10). | 해당 이벤트를 추가한 메모리 변이가 Q2-C3 및 전체 검사에서 통과함. | 개인정보 의미를 포괄하는 금지 패턴/명시적 안전 이벤트명 목록을 추가하고 변이 테스트한다.

major | tools/validate_graph.py:559-583; specs/analytics/events.yaml:40-44 | 북극성 지표의 “매 세션”, “서버 확인 월드 결과”, `expression_used=label`, 세션당 1회 조건이 자유 문구·조건 토큰에만 있어 실제 이벤트 의미와 연결되지 않는다. | `session_start.when`을 사용자당 1회로, `term_reused.when`을 클라이언트 이벤트로 바꿔도 전체 검사가 통과함. | 이벤트 조건을 구조화된 필드로 만들고 서버 판정·label 필터·세션당 dedupe를 기계적으로 검사한다.

major | tools/validate_graph.py:762-768; tests/test_q2_graph.py:620-623 | 힌트가 목표 표현의 단어·순서를 바꾸어 사실상 정답을 말해도 exact substring 검사라 통과한다. | `hint.coordinate.l2`를 `위 1, 오른쪽 2로 보내면 돼.`로 바꾸면 Q2-C7 전체 검사가 통과함. | 목표 표현의 구성 요소·동의 표현을 구조화해 힌트 금지 검사를 추가하고 순서 변경 변이를 테스트한다.

major | tools/validate_graph.py:820-863; tests/test_q2_graph.py:565-705 | 모든 미션을 선택 미션으로 바꾸고 `target_end_s`를 null로 만들면 필수 경로가 사라지는데 Q2-C7이 통과한다. | 모든 mission의 `core=false`, `target_end_s=null` 변이에서 Q2-C1~C7이 모두 빈 오류 목록을 반환함. | `core` 필수 미션이 최소 하나이고 용어 도입·시나리오가 그 경로에 포함되는지 강제하는 검사와 변이 테스트를 추가한다.
