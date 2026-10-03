major | harness/checks/server.py:185-211 | `claimOnce`가 이미 지급된 경우 실제로 거부하지 않아도 통과한다 | `if claimed[slot] then warn(...) end` 뒤 별도 조건의 `return false`와 `claimed[slot] = true`를 두면 `duplicate_reward`가 빈 결과 | 읽기·거부·동일 슬롯 기록의 제어흐름 연결을 검사

major | harness/checks/server.py:692-727 | `coordinateMove(...) == nil` 같은 거짓/불확정 조건의 가지 안 보상이 판정 성공으로 통과한다 | 해당 조건으로 clean fixture를 변형해 `reward_after_verdict`가 빈 결과 | 판정 호출 단독 또는 명시적 성공 조건만 허용하고 나머지 비교는 거부

major | harness/checks/server.py:153-156; harness/resolve.py:207-233 | 보상 함수를 두 단계 별칭으로 만든 뒤 값으로 넘기면 보상·판정 검사를 모두 우회한다 | `R.grant → g → h; pcall(h, player, ...)` 변형에서 `duplicate_reward`·`reward_after_verdict` 모두 빈 결과 | `passed_as_value` 대상에 `_grant_aliases`의 단일 이름 별칭도 포함하거나 미해석 함수값을 거부

major | harness/checks/analytics.py:71-82; harness/resolve.py:207-233 | 분석 전송 함수를 두 단계 별칭으로 만든 뒤 값으로 넘기면 허용 목록 검사를 우회한다 | `Analytics.log → send → send2; pcall(send2, ..., "not_allowed", {})` 변형에서 `analytics.calls`가 빈 결과 | 분석 메서드 별칭을 값 전달 검사에도 확장하거나 미해석 함수값을 거부

major | harness/checks/i18n.py:33-48,69-85 | 번역 함수 별칭을 값으로 넘겨 끊긴 키를 호출해도 `missing_key`가 통과한다 | `Text.get → get → use; pcall(use, "goal.missing")` 변형에서 `missing_key`·`hardcoded_text` 모두 빈 결과 | 문구 함수 별칭의 고차 함수 전달을 추적하거나 미해석 전달을 거부

major | harness/checks/math_claims.py:128-143,193-217 | `line_point`가 직선식의 계수 관계가 아니라 m·b 숫자의 개별 출현만 확인한다 | 원문을 `y = 1x + 2`로 바꿔도 명제 `y = 2x + 1`에 대해 `math.truth`가 빈 결과 | 정수 계수도 구조화된 식 전체(`line_text`) 또는 언어 중립적 식 관계를 검증하고 계수 순열 회귀시험 추가
