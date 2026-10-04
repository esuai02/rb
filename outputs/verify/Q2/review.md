major | tools/validate_graph.py:52-54,968-971 | `other_result_x3` 재도전이 실제 다른 월드 결과를 선언하는지 검사하지 않는다 | `world_response.other_result_key`가 선택 항목이고 시나리오는 시도 수만 `>=3`인지 확인한다. 두 수학 미션의 대체 결과 키와 문구를 함께 제거해도 모든 Q2 검사가 통과한다 | 수학 미션의 대체 결과·outcome을 필수 구조화하고 변이 테스트 추가

major | tools/validate_graph.py:975-1008 | per-occurrence 이벤트의 발생 횟수를 검사하지 않는다 | `expects_events`와 `implied_events`가 집합으로 비교된다. 첫 시나리오는 두 수학 미션·두 재사용 맥락을 지나지만 `math_attempt`, `label_shown`, `term_reused`를 각각 한 번만 기록한다(events.yaml:42,44,45) | 이벤트 기대값을 맥락·용어별 발생 레코드/개수로 구조화하고 정확한 다중 발생을 검증
