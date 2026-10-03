critical | harness/checks/server.py:166-172,198-205 | 미해석 대괄호에 함수 이름을 대입한 원격 처리(`Remote[method] = handler`)를 핸들러로 수집하지 않아 타입·범위·쿨다운 검사를 모두 우회한다 | 대괄호 RHS가 `function`일 때만 거부하고 이름 RHS는 무시한다 | 미해석 대괄호 대입은 RHS가 함수 이름이어도 무조건 거부한다

critical | harness/checks/server.py:134-139 | `claimOnce`라는 이름의 호출 모양만 확인해 실제 구현이 항상 `true`를 반환하는 no-op이어도 중복 보상 검사를 통과한다 | `local function claimOnce(...) return true end`를 둔 `grant`가 빈 결과가 된다 | `claimOnce` 구현의 상태·재호출 차단을 구조적으로 검증하거나 검증 불가 시 거부한다

major | harness/checks/i18n.py:198-202 | 유효한 문구 키 호출이 RHS 앞 12토큰 안에 있으면 뒤의 미해석 조립·함수 결과를 전부 건너뛴다 | `Text.get("goal.signal_2") .. a .. b .. c .. d .. e .. unknownValue()`가 `i18n.hardcoded_text`에서 검출되지 않는다 | RHS 전체가 허용된 단일 키 호출인지 확인하고, 뒤의 미해석 토큰은 거부한다

minor | tests/test_harness.py:250-257 | 진단 문구 검사가 각 검사 결과의 전체 진단을 검증하지 않고 첫 예상 검사에서 한 조각만 찾으므로, 의도하지 않은 진단이 추가되어도 통과한다 | `found[expected[0]]`에서 `fragment` 포함 여부만 검사한다 | 결함별 기대 진단 ID·메시지 집합을 비교해 추가·대체 진단을 실패시킨다
