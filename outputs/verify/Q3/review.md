major | harness/checks/analytics.py:105 | 분석 모듈의 해석 불가능한 이벤트명이 통과한다 | `local event = getEvent()`을 플랫폼 API에 전달해도 `literals`가 비어 오류가 없다. 허용 이벤트인지 판정할 수 없다 | 이벤트·단계·필드를 정적으로 해석하지 못하면 거부한다

major | harness/checks/i18n.py:153 | 알 수 없는 UI 문자열 조립이 통과한다 | `local msg = getA() .. getB(); label.Text = msg`가 `i18n.hardcoded_text` 0건이다. 현재는 대입 RHS에 `..`가 있을 때만 거부한다 | UI 대입값이 Localization 호출 또는 해석 가능한 값이 아니면 점·대괄호 모두 거부한다

major | harness/checks/server.py:97 | 플레이어 별칭의 동적 보상 권한 접근이 통과한다 | `local p = player; local key = getKey(); p[key] = value`가 `server.reward_authority` 0건이다. 동적 멤버 검사가 원래 변수명만 본다 | 해석 가능한 플레이어 별칭까지 동적 멤버 검사 대상에 포함한다

major | harness/checks/server.py:390 | 재할당된 범위 상수를 정본 값으로 오인한다 | 함수 뒤 `GRID = 9999`로 재할당해도 `f.resolved`의 `GRID=2`를 사용해 계약 범위 검사가 통과한다 | 재할당을 정확히 추적해 범위 경계를 해석 불가로 거부하거나 실제 최종 바인딩을 검증한다
