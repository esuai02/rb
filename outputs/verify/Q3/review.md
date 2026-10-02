major | harness/checks/server.py:16-30 | 직접 `require(...).grant(...)` 호출이 보상 중복·판정 검사를 우회한다 | 모듈 별칭만 탐색하며 직접 require 경로는 `grant_calls`에 포함되지 않는다. 원격 핸들러의 직접 호출을 추가해도 세 서버 검사가 빈 결과를 반환함 | 직접 require 멤버 경로를 해석하거나, 해석 불가 시 거부

major | harness/checks/analytics.py:19-20 | 직접 `require(...).log/funnel(...)` 호출이 허용 이벤트·필드 검사를 우회한다 | `_aliases`가 로컬 별칭만 수집하고 직접 require 호출은 `_check_call`에 전달하지 않는다 | 직접 require 결과의 메서드 호출도 분석 호출로 수집

major | harness/checks/i18n.py:29-45 | 직접 `require(...).get("없는 키")`가 번역 키 검사를 우회한다 | `_key_calls`가 모듈 별칭 기반 경로만 찾으므로 직접 require의 `get` 호출은 `missing_key`에서 누락된다 | 직접 require 멤버 호출을 키 호출로 해석하거나 불확실하면 거부

major | harness/checks/server.py:223-225,461-466 | 표 입력의 동적 필드 `payload[key]`가 형식·범위 검사 없이 통과한다 | `_fields_used`는 점 표기와 정규화된 고정 대괄호만 수집하며, 동적 대괄호 필드는 0개로 처리한다. 동적 필드 원격 핸들러를 추가해 `remote_validation`이 빈 결과를 반환함 | 표의 미해석 멤버 접근을 명시적으로 거부

major | harness/checks/safety.py:83-95,125-143 | 문자열 조립으로 만든 `HttpService`·`MarketplaceService`가 외부/유료 검사에서 누락된다 | `GetService` 인자는 문자열인지 여부만 확인하고, 보안 이름 검사는 원본 토큰만 비교한다. `local a="Http"; local b=a.."Service"; game:GetService(b)`가 빈 결과를 반환함 | 해석된 문자열 값도 금지 목록과 비교하고, 해석 불가한 서비스명은 거부

minor | harness/checks/i18n.py:16,236-240 | 전각 `！`·`？` 및 공백 없는 문장 경계를 문장 수로 세지 않는다 | `SENTENCE_END`가 `. ! ? 。` 일부만 지원하고 뒤의 공백을 요구한다 | Unicode 문장 종결자와 줄바꿈·무공백 경계를 포함해 문장을 분리
