major | harness/checks/server.py:48 | 보상 도달 분석이 고정 6회만 전파되어 7단계 이상 헬퍼 호출을 놓친다 | 선언 순서를 역순으로 둔 `h0→…→h7→RewardService.grant` 변형이 판정 없는 원격 처리임에도 18개 검사 모두 통과했다 | 이름 집합이 더 이상 변하지 않을 때까지 고정점 반복하고 장거리 헬퍼 회귀 테스트 추가

major | harness/checks/server.py:678 | 판정 내부에서 보상하는 헬퍼를 전역적으로 안전하다고 분류해 판정 없는 호출 경로를 놓친다 | `finish()` 내부에 판정·보상을 넣고 원격 핸들러에서 `finish()`를 무조건 호출한 변형이 `server.reward_after_verdict`를 통과했다 | 함수 자체가 아니라 호출 경로별 판정 도달성을 분석하고 무조건 호출 회귀 테스트 추가

major | harness/checks/math_claims.py:220 | 구조적으로 잘못된 명제 입력이 검사 중 예외를 일으킨다 | `line_key: [label.coordinate.line]`인 파싱 가능한 명제에서 `tree.strings.get()`이 `TypeError: unhashable type: list`를 발생시켜 검사 중단 기록이 남는다 | 명제 스키마를 읽을 때 검증하고 `line_key`·`line` 등의 형식 오류를 진단 목록으로 반환하도록 가드 추가
