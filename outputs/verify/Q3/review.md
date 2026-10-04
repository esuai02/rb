major | harness/checks/analytics.py:194-215 | 동적 키로 CustomField04 등 허용 밖 분석 칸을 보낼 수 있다 | `custom[slot] = "bad"`에서 `slot`이 `"CustomField04"`여도 `_custom_field_errors`가 대괄호 동적 대입을 검사하지 않는다. clean 트리의 메모리 변형에서 `analytics.calls`가 빈 결과였다 | 동적 플랫폼 칸 대입은 정적으로 허용 목록에 증명되지 않으면 거부한다

major | harness/checks/analytics.py:168-190 | 분석 모듈이 `player:GetAttribute("School")` 같은 개인정보를 필드에 넣어도 통과한다 | 개인정보 검사는 알려진 속성명(`Name`, `UserId` 등)만 직접 점 표기로 찾고 `GetAttribute` 결과·대입은 추적하지 않는다. 해당 메모리 변형에서 `analytics.calls`가 빈 결과였다 | 플레이어 속성/속성 조회 결과의 분석 전파를 금지하거나 정적으로 열거형임을 증명하지 못하면 거부한다

major | harness/checks/server.py:104-126 | 보상 모듈 밖의 임의 `SetAttribute("reward.explorer_badge", true)` 지급을 잡지 못한다 | 권한 검사는 유한한 `authority_names` 토큰과 동적 멤버 읽기만 검사하며 `SetAttribute` 쓰기를 보지 않는다. MissionService의 해당 메모리 변형에서 `server.reward_authority`, `server.duplicate_reward`, `server.reward_after_verdict`가 모두 빈 결과였다 | 보상·경험치·자격 상태에 대한 Player/하위 객체 쓰기는 신뢰 보상 모듈 밖에서 거부한다
