major | harness/checks/server.py:161-192 | `claimOnce`가 실제 중복 방지를 보장하지 않는 코드도 통과한다 | 토큰 순서만 확인해 `return true` 뒤의 `claimed[slot] = true`를 유효한 기록으로 인정하며 제어흐름을 검사하지 않음 | 쓰기 연산이 모든 성공 반환을 지배하는지 제어흐름 분석으로 검증

major | harness/checks/safety.py:48-67,70-74 | 알려진 키 접두어를 가진 외부 도메인이 URL 검사에서 누락된다 | `known_ids()`가 `goal`을 접두어로 만들고 `_domain()`이 `goal.museum`을 도메인이 아니라고 반환함 | 전체 식별자와 도메인을 구분하거나, 접두어만 같아도 미확인 도메인은 거부

major | harness/checks/i18n.py:167-172,233-239 | 동적 UI 속성에 함수 결과를 대입하면 화면 문구 검사를 우회한다 | `goal[prop] = function() return "Ready" end`에서 함수 대입을 무조건 예외 처리하고, `"Ready"`도 식별자 형태라 하드코딩 검사에서 제외됨 | 원격 이벤트에 대한 예외만 허용하고 동적 UI 속성은 항상 거부

major | harness/checks/safety.py:164-175 | `Instance.new` 별칭을 통한 알 수 없는 자유 입력 인스턴스 생성이 통과한다 | `local make = Instance.new; make(getClass())`는 직접 `Instance.new` 호출도 `TextBox` 토큰도 없어 결과가 빈 목록임 | `Instance.new` 별칭을 추적하고 클래스명이 해석되지 않으면 거부
