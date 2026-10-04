minor | tests/test_validate_spec.py:91 | Q1-C1 테스트는 필드 삭제만 검사해 `language_goals: []`·`do_not_translate: []`를 허용하는 회귀를 놓친다 | schema의 `minItems`가 제거돼도 현재 테스트는 통과한다 | 두 배열을 빈 목록으로 바꾸는 실패 변이를 추가

minor | tests/test_validate_spec.py:98 | Q1-C3 테스트는 중첩된 혼합 키를 검사하지 않는다 | `market.locale` 또는 `audience.market_id` 변이를 추가해도 현재 테스트는 통과하며, 중첩 `additionalProperties: false`가 제거되면 잘못된 키가 통과한다 | 시장·언어·교육과정 혼합 키 변이 테스트를 추가
