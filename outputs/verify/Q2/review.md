major | tools/validate_graph.py:60 | 단계별 필수 문구 키가 선택 항목이라 핵심 미션 단계가 빈 상태로 통과할 수 있다 | `situation/world_response/interaction`의 `key`를 제거하고 해당 비-Q1 문자열을 삭제해도 전체 검사 통과 | 단계 종류별 필수 필드 검사와 변이 테스트 추가
major | tools/validate_graph.py:373-375 | 보상·힌트·역할·시나리오 ID 중복을 검사하지 않아 참조가 모호해진다 | 동일 reward/ladder/role/scenario 객체를 추가해도 검사 통과; 테스트는 mission/term/context 중복만 다룸 | 모든 ID 보유 목록의 고유성 검사와 각 변이 테스트 추가
minor | tools/validate_graph.py:599-620 | canonical `source`가 실제 K0 문서를 가리키는지 검사하지 않는다 | `canonical-values.yaml:9`의 source를 임의 문자열로 바꿔도 전체 검사 통과 | `source == K0_PATH` 검증 및 변이 테스트 추가
