major | tools/validate_graph.py:142-148,689-691 | 가설 수치 범위 검사가 `cv.first_try.success_within_two_tries`를 누락한다 | 값을 `[0.1, 0.2]`로 바꿔도 전체 검사가 통과하지만 K6 R2·canonical rationale은 70~90%를 요구한다 | 해당 범위를 검사하고 변이 테스트 추가

minor | tools/validate_graph.py:360-363,440-443 | Graph의 `events` 경로를 고정하지 않아 다른 이벤트 목록으로 우회 가능하다 | `graph.events = "other.yaml"` 변이에서 Q2-C1 오류가 발생하지 않는다 | `specs/analytics/events.yaml` 경로 고정 및 변이 테스트 추가
