major | harness/resolve.py:14-35 | 줄바꿈된 별칭 RHS를 `UNRESOLVED`로 잘못 끊어 검사 우회가 가능하다 | `local g =\n RewardService.grant; g(...,"evil_reward",...)`가 `server.duplicate_reward=[]`; 동일 방식의 `Text.get`·`Analytics.log` 별칭도 각각 빈 결과 | 줄바꿈을 포함한 식을 구조적으로 해석하거나 해석 불가 별칭을 거부

major | harness/checks/safety.py:168-175 | `GetService` 결과 별칭을 같은 줄의 `local` 선언만 추적한다 | `local svc\nsvc = game:GetService("SomeService")` 뒤 `svc[chooseMethod()]({})`에서 `_service_names=set()` 및 `external_call=[]` | 모든 대입 형태의 서비스 별칭을 추적하고 동적 멤버는 거부

major | harness/run.py:88-95 | 기록 경로 제거가 Windows 경로와 공백 포함 Unix 경로를 완전히 제거하지 못한다 | `C:\Users\Alice\project\src`는 그대로 남고 `/home/alice/My Project/file.txt`는 `<path> Project/file.txt`로 잔존 | Windows·공백 경로를 포함하는 견고한 scrubber를 사용하거나 원문 경로를 기록하지 않기
