critical | harness/checks/server.py:217-223 | 미해석 동적 원격 멤버에 미해석 핸들러를 대입해도 원격 검사가 생략된다 | `local h = require(...).makeHandler(); SignalRemote[key] = h`에서 `_is_function_value`가 거짓이어서 `_handlers`가 빈 결과를 반환한다 | 동적 멤버 대입의 RHS가 확정적으로 비함수임을 증명하지 못하면 무조건 거부한다

major | harness/checks/server.py:161-179 | `claimOnce`가 읽는 키와 기록하는 키의 동일성을 검사하지 않아 중복 보상을 통과시킨다 | `if claimed[slot] then return false end; claimed[slot .. "|mark"] = true; return true`가 오류 없이 통과한다 | 읽기·쓰기 키 식과 제어 흐름이 동일한지 검증하고 불명확하면 거부한다

major | harness/checks/analytics.py:50-60,126-156 | 신뢰된 분석 모듈의 `pack`이 허용 목록 밖 필드나 4번째 필드를 추가해도 검출하지 못한다 | `custom["CustomField04"] = "fixed"`를 `pack`에 추가한 변형에서 `analytics.calls`가 빈 결과를 반환한다 | 분석 모듈의 최종 전송 표를 분석해 허용 필드·최대 3개·열거형 값만 허용한다
