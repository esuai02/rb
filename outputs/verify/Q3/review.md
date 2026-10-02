major | harness/checks/server.py:107-114 | `grant`의 `claimOnce`가 실제 호출인지 확인하지 않아 중복 보상 방지 없는 코드가 통과한다 | `if not claimOnce then return end`도 동일한 토큰 형태로 인정되어 `server.duplicate_reward`가 빈 결과가 됨 | `claimOnce(...)` 호출·인자·반환값을 구조적으로 확인하고 회귀 결함 추가

major | harness/checks/server.py:494-510 | 판정 함수를 한 번이라도 호출한 함수 전체를 안전한 보상 함수로 간주한다 | 같은 함수에서 판정의 거짓 경로 뒤에 `RewardService.grant`를 두어도 `self_verdicting`에서 제거되어 `server.reward_after_verdict`가 통과함 | 함수·호출 경로별로 보상이 판정의 참 가지 안에 있는지 추적

major | harness/checks/server.py:304-325,415-422 | 범위 검사가 타입 검사보다 앞서도 검증 완료로 인정한다 | 범위 가드를 먼저 두고 `typeof`를 뒤에 둔 변형에서 `server.remote_validation`이 빈 결과 | 타입 가드 위치가 모든 범위 가드·입력 사용보다 앞서는지 검사

major | harness/checks/i18n.py:33-59 | 알 수 없는 동적 문구 함수 멤버를 거부하지 않는다 | `Text[method]("goal.missing")`에서 `method`가 미해결이어도 `i18n.missing_key`와 `i18n.hardcoded_text`가 모두 빈 결과 | 문구 모듈의 미해결 `[...]` 호출을 검사 실패로 처리

major | harness/checks/analytics.py:53-73,91-104 | 동적 분석 멤버와 플랫폼 전송 함수 별칭을 검사하지 않는다 | `Analytics[method](...)` 및 `local send = AnalyticsService.LogCustomEvent; send(..., "player_profile", ...)`가 `analytics.calls`를 통과함 | 미해결 분석 호출을 거부하고 플랫폼 API 별칭까지 해석·검사

major | harness/checks/server.py:27-29,515-517 | 대괄호로 선택한 보상 함수를 보상 호출로 인식하지 않는다 | `RewardService[method](player, "reward...", "mission...")`가 `server.duplicate_reward`·`server.reward_after_verdict` 모두 통과함 | 보상 모듈의 미해결 동적 멤버 호출을 실패로 처리

major | harness/checks/safety.py:10,34-37 | URL 검사가 모든 URL 형식과 도메인을 포괄하지 않는다 | LocalizationTable의 `ftp://example.xyz`가 `safety.url`에서 검출되지 않음 | URI 스킴·호스트를 일반적으로 판정하는 URL 검사를 사용하고 회귀 데이터 추가
