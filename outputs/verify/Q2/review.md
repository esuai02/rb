major | tools/validate_graph.py:392-405; tests/test_q2_graph.py:222-234 | 북극성 지표가 반드시 `term_reused ÷ session_start`인지 검사하지 않는다 | `label_shown`을 분자, `hint_shown`을 분모로 바꾸고 필드를 맞춰도 `check_events()`가 빈 오류를 반환한다 | 분자·분모 이벤트 ID를 각각 `term_reused`·`session_start`로 고정하고 변이 테스트 추가

major | specs/graph/neo-seoul-city-language-gate.graph.json:83-108; tools/validate_graph.py:559-565 | 재사용 맥락을 가진 수학 미션 4개에 자기 힌트 사다리가 없지만 검사기가 `new_term` 미션만 검사한다 | 해당 미션들의 사다리를 모두 제거해도 전체 Q2 검사 통과 | 수학 행동/재사용 맥락을 가진 모든 미션에 사다리 요구 및 변이 테스트 추가

major | tools/validate_graph.py:437-440; specs/graph/canonical-values.yaml:45-51 | `decided` 값의 `Q1` 근거가 실제 잠긴 Q1 항목인지 검증하지 않는다 | `cv.match_wait`를 `status: decided`, `refs: [Q1]`로 바꾸면 `check_canonical()` 통과 | 값별 Q1 경로 또는 실제 결정 근거를 명시·검증

major | specs/graph/canonical-values.yaml:9-15; tools/validate_graph.py:427-440; tests/test_q2_graph.py:326-383 | 정본 값의 중첩 `value`가 자유 객체라 가격·확률 등 모르는 항목을 삽입해도 통과한다 | `cv.hold_time.value.price = 1` 변이가 모든 Q2 검사에서 오류 없이 통과 | 정본 값별 허용 필드 스키마와 금지 필드 변이 테스트 추가

minor | tools/validate_graph.py:210-212; tests/test_q2_graph.py:63-86 | Q1 용어 ID의 중복 항목을 집합 비교가 허용한다 | Graph의 `terms`에 기존 용어를 복제해도 `check_references()` 통과 | 용어 목록 길이와 ID 유일성을 함께 검증

minor | tools/validate_graph.py:585-586; specs/graph/neo-seoul-city-language-gate.graph.json:135-137; tests/test_q2_graph.py:543-546 | 정지점의 두 선택지가 서로 다른 `계속/쉬기`인지 검증하지 않는다 | `choice_keys`를 `[pacing.continue, pacing.continue]`로 바꿔도 통과 | 정확히 `{pacing.continue, pacing.rest}`인지 검사하는 변이 테스트 추가
