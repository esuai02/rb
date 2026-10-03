major | harness/checks/analytics.py:161 | 분석 모듈의 `log`/`funnel`이라는 이름만 맞춘 보조 함수가 허용 밖 이벤트를 전송해도 통과한다 | 신뢰된 모듈은 호출부 검사를 건너뛰고(56–61), 함수의 마지막 이름만 검사한다(132–139). `local function log(...)`에서 `LogCustomEvent(..., eventName, ...)` 후 `log(nil, "not_allowed")`를 호출해도 `analytics.calls=[]` 재현됨 | `Analytics.log`·`Analytics.funnel`의 정규 메서드 선언만 허용하고 해당 우회 회귀시험 추가

major | outputs/verify/Q3/LOCK-Q3.txt:3 | Q3-6V 검토가 잠금 전에 최종 산출물에 대해 기록되지 않았다 | 잠금 binding은 `b649f2ed...`(07:48)인데 최신 Q3-6V 기록은 `c632cefa...`(13:23)로 잠금 후이며, graph.json:618도 이전 binding을 가리킨다 | 최종 binding으로 Q3-6V를 다시 기록한 뒤 Q3를 재잠금할 것
