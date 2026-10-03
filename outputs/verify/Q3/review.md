major | harness/checks/safety.py:89-94 | 여러 변수로 조립한 `GetService` 외부 서비스명이 통과한다 | `local a="Http"; local b="Service"; game:GetService(a..b)`의 해석값은 문자열이지만 `names`와 대조하지 않는다. 동일 결함이 현재 고정 결함 목록에도 없다(tests/test_harness.py:63) | `GetService` 해석값이 `external_call_names`이면 거부하고 다단계 조립 회귀시험을 추가

major | harness/checks/safety.py:130-133 | 여러 변수로 조립한 유료 서비스와 게임패스 권한 검사가 통과한다 | `game:GetService(a..b):UserOwnsGamePassAsync(...)`에서 분리된 문자열은 `paid_names`에 없고 GetService 인자를 검사하지 않는다. `paid_names`에도 해당 메서드가 없다(harness/manifest.json:67-73) | 유료 서비스명과 권한 메서드의 해석값을 검사 목록에 추가하고 회귀 결함을 추가
