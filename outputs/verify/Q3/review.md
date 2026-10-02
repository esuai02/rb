major | harness/checks/analytics.py:99-105 | 분석 모듈이 이벤트를 상수 변수에 담아 플랫폼 API로 보내도 통과한다 | `local BAD = "not_allowed"; LogCustomEvent(..., BAD, ...)`에서 `analytics.calls`가 `[]`를 반환하며, 테스트는 직접 문자열만 검증한다 | 플랫폼 API의 이벤트·필드 인자가 함수 매개변수에서 전달되는지 또는 허용 목록과 정적으로 일치하는지 검증

major | harness/checks/safety.py:112-117 | 난수 API를 모듈·변수 별칭으로 호출하면 무작위 보상 검사가 통과한다 | `local m = math; local r = m.random; r()`에서 `random_or_paid_reward`가 `[]`를 반환한다 | `f.resolved`의 `("math", "random")`·`("Random", "new")` 경로 별칭도 호출 검사에 포함하거나 해석 불가 호출을 거부

minor | harness/checks/i18n.py:153 | 알 수 없는 UI 문자열 조립 결함이 의도한 검출이 아니라 `NameError`로 실패한다 | `unresolved_ui_text`가 import하지 않은 `SYMBOL`을 참조하며, 해당 결함 실행 시 `검사가 끝까지 돌지 못했다 (NameError...)`가 기록된다 | `from harness.luau import NAME, STRING, SYMBOL`로 가져오고 회귀 테스트에서 구체적 UI 조립 진단을 확인
