major | harness/checks/analytics.py:92-95 | 분리 대입한 분석 함수 별칭이 허용 이벤트·필드 검사를 우회한다 | `local send; send = Analytics.log; send(..., "player_profile", ...)`에서 `analytics.calls`가 `[]`이며 `resolve`가 비지역 재대입을 추적하지 않는다 | 분리 대입도 추적하거나 해석 불가 함수 호출을 거부

major | harness/checks/server.py:20-30 | 분리 대입한 보상 별칭이 중복 보상·판정 후 보상 검사를 우회한다 | `local grant; grant = RewardService.grant; grant(...)`인 원격 처리에서 `server.duplicate_reward`와 `server.reward_after_verdict`가 모두 `[]` | 별칭 해석을 보강하거나 해석 불가 보상 호출을 거부

major | harness/checks/safety.py:84-93 | 여러 분리 대입으로 조립한 외부 링크가 통과한다 | `https`, `://`, `example`, `.`, `com`을 각각 대입해 연결하면 `safety.url`이 `[]`; 미해석 연결식에는 URL 조각이 없어 거부하지 않는다 | 상수 대입을 추적하거나 미해석 문자열 연결을 URL 여부와 무관하게 거부

major | harness/source.py:191-211 | 문법적으로 닫히지 않은 최상위 Luau 블록을 읽기 성공으로 처리한다 | `_load_file`은 토큰화만 하고 전체 블록 검사를 호출하지 않으며, `function_bodies`는 함수 내부만 검사한다 | 모든 Luau 파일에 블록·구문 검증을 적용하고 실패를 `Tree.problems`로 기록

major | tests/test_harness.py:290-341 | Q3-C1의 168 결함 종류 완전성은 검증되지 않는다 | `REQUIRED_CLASSES`는 20종뿐이고, 나머지는 현재 매니페스트 클래스가 기준문에 포함되는지만 검사한다. 기준문에 적힌 결함을 매니페스트·독립표에서 함께 제거해도 통과 가능하다 | 전체 168종의 별도 고정 집합과 매니페스트·진단표의 정확한 동치 검증 추가
