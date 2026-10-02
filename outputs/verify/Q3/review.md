major | harness/checks/math_claims.py:116-122,149-167 | 좌표 명제의 분수 이동량이 대사에 없어도 통과한다 | `right 1/2` 후 `left 1/2`, 결과 `(0, 0)`인 명제는 이동량 검사가 없어 `truth`가 빈 결과를 낸다 | 모든 이동량의 분수·소수도 대사 연결을 요구하고 검사한다

major | harness/checks/analytics.py:57-59,125-140 | 분석 모듈 내부에서 플랫폼 전송 함수를 별칭으로 바꾸면 퍼널을 CustomEvent로 보내도 통과한다 | `local send = AnalyticsService.LogCustomEvent` 후 `Analytics.funnel`에서 `send(...)`를 호출해도 직접 `API(`만 검사하므로 `calls`가 빈 결과를 낸다 | 플랫폼 API 별칭을 해석해 래퍼별 실제 전송 함수를 검증하고 미해석 시 거부한다

major | harness/checks/server.py:149-166 | 원격 객체를 미해석 변수로 받아 `evt:Connect(...)`하면 원격 검증·쿨다운·판정 검사가 모두 건너뛴다 | `_handlers`는 `OnServerEvent`·`OnServerInvoke` 또는 특정 대괄호 형태만 찾으며 `evt = getRemoteEvent(); evt:Connect(...)`는 빈 처리 목록이 된다 | 미해석 연결 수신자는 거부하거나 정본 RemoteEvent/RemoteFunction 형태만 허용한다

major | harness/source.py:47-48; harness/checks/server.py:86-96 | `RewardService.server.luau` 같은 Script가 이름만으로 보상 모듈로 신뢰되어 권한 검사를 피한다 | `name`이 첫 점 앞까지만 반환되고 `reward_authority`는 `f.name == module`이면 건너뛴다 | 보상 모듈을 ModuleScript·정확한 서버 경로·단일 소유자로 검증하고 나머지는 모두 검사한다

major | harness/checks/safety.py:81-85 | 외부 서비스와 메서드를 미해석 변수·동적 멤버로 호출해도 외부 호출 검사를 통과한다 | `game:GetService(serviceName); svc[methodName]({})`에는 설정된 이름 토큰이 없어 `external_call`이 빈 결과를 낸다 | 동적 `GetService`·멤버 호출은 거부하고 허용된 리터럴 서비스·메서드만 통과시킨다
