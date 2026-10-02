major | harness/checks/server.py:162-196 | 동적 멤버로 등록한 RemoteFunction을 원격 검증·쿨다운 검사 없이 통과시킨다 | `SignalRemote[method] = function(...) ... end`는 `_handlers`가 `OnServerEvent`·`OnServerInvoke` 고정 토큰만 찾아 모두 `[]`를 반환한다 | 미해석 대괄호 멤버를 함수 핸들러로 대입하는 경우도 거부하도록 `_handlers`에 보수적 진단을 추가한다

major | harness/checks/analytics.py:53-60,130-147 | 분석 모듈 내부의 미해석 플랫폼 멤버 호출이 허용되어 이벤트 검사를 우회한다 | `AnalyticsService[method](player, eventName, 1, pack(fields))`가 `analytics.calls`에서 발견 0건이다 | 정식 분석 서비스의 동적 멤버 접근을 모두 거부하고, 허용된 플랫폼 API의 직접 호출만 인정한다

major | harness/checks/i18n.py:194-206 | UI 문구가 미해석 대괄호 호출 결과로 들어가도 현지화 검사를 우회한다 | `goal.Text = translator[method]("goal.signal_2")`가 `i18n.hardcoded_text`·`i18n.missing_key` 모두 발견 0건이다 | RHS의 대괄호 호출을 일반 함수 호출로 판정하지 말고, 문구 키 호출로 확정되지 않은 호출 결과는 거부한다
