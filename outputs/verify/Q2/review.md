major | specs/graph/neo-seoul-city-language-gate.graph.json:466-470; tools/validate_graph.py:329-334 | `coop.plaza_bridge.objects`의 `plaza_bridge_left/right`가 Q1·용어집·정본 값에 정의되지 않았고 임의 객체 ID로 바꿔도 PASS한다 | 모든 협동 객체를 정본 ID로 등록·검증하고 unknown-object 변이 테스트 추가

major | tools/validate_graph.py:519-524; tests/test_q2_graph.py:384-389 | `decided` 값은 관련성 없는 결정된 DEC를 근거로 써도 통과한다. `cv.match_wait`를 `refs: [DEC-1]`로 바꿔도 PASS한다 | K0 행별 허용 DEC와 결정 내용을 검증하고 관련 없는 DEC 변이 테스트 추가

major | tools/validate_graph.py:474-484; tests/test_q2_graph.py:226-243 | 북극성 조건에 임의 조건을 추가해도 통과하여 지표 정의가 조용히 바뀐다 | `counts_only_when`를 요구 집합과 정확히 비교하고 추가 조건 변이 테스트 추가

major | tools/validate_graph.py:40-41,576-588; tests/test_q2_graph.py:432-435 | 금지어 검사가 부분 집합만 강제한다. `테스트`를 금지 목록에서 제거하고 문구에 넣어도 PASS한다 | 금지어 전체 집합을 닫힌 목록으로 강제하고 각 금지어 제거·문구 삽입 변이 테스트 추가

minor | tools/validate_graph.py:685-696; tests/test_q2_graph.py:573-614 | `target_end_s`의 음수·0을 거부하지 않아 `-1`로 바꾼 필수 미션도 시간 기준을 통과한다 | 목표 시간에 `0 <= target_end_s` 검사를 추가하고 음수 변이 테스트 추가
