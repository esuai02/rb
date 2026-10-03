major | harness/checks/i18n.py:35-36,48-64,230-236 | Text 모듈 내부의 끊긴 번역 키를 검사하지 않는다 | `Text` 모듈의 `FormatByKey("goal.missing")`가 `missing_key=[]`, 식별자형 문자열이라 `hardcoded_text=[]` | Text 모듈에서도 리터럴 키 호출은 LocalizationTable 존재 여부를 검사하고, 매개변수 전달만 예외 처리

major | harness/checks/analytics.py:53-60,132-147 | 신뢰된 Analytics 모듈의 보조 함수가 허용 밖 이벤트를 전송해도 통과한다 | 모듈 내부 `raw(player,eventName)`가 `LogCustomEvent(...,eventName,...)`를 호출하고 `raw(nil,"not_allowed")`를 호출해도 `analytics.calls=[]` | 플랫폼 API 호출을 `Analytics.log`·`Analytics.funnel` 구현으로 제한하거나 보조 함수 호출까지 허용 이벤트로 추적 검사
