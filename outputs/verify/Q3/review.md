major | harness/source.py:194 | 짝이 맞지 않는 `()[]{}`를 읽기 성공으로 처리한다 | `local x = (`는 `block_balance`가 0이고 `Tree.problems`도 없어, 깨끗한 트리에 추가해 18개 검사가 모두 빈 결과를 냈다 | 파일 적재 전에 구분자 스택을 검사해 불일치·미종결이면 거부

major | harness/checks/safety.py:76 | `grant` 호출의 모든 문자열을 URL 검사에서 제외한다 | `RewardService.grant(..., "https://evil.example", ...)`를 넣어도 `safety.url` 결과가 `[]`이며, `server.duplicate_reward`는 임의 문자열 ID를 허용한다 | 허용된 보상·미션 ID만 제외하고 나머지 인자는 URL 검사

major | harness/checks/server.py:117 | 이름을 바꾼 `Player` 매개변수의 동적 권한 접근이 통과한다 | 클라이언트 코드에 `function mutate(actor: Player) actor[key] = 1 end`를 추가해도 `server.reward_authority`가 빈 결과를 냈다 | 타입이 `Player`인 매개변수와 별칭도 `_player_like`에 포함하고 미해결 멤버를 거부

minor | harness/checks/server.py:503 | 잘못된 원격 계약 항목에서 검사기가 예외로 중단된다 | `tree.contracts={"SignalRemote":[1]}`에서 `remote_validation`이 `AttributeError: 'int' object has no attribute 'get'`를 냈다 | 비객체 계약 항목은 진단 후 해당 파라미터 검사를 건너뛰어 검사 중단을 없앰
