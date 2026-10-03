major | harness/checks/i18n.py:46-48,235-236 | 임의 객체의 `:FormatByKey("goal.signal_2")`를 LocalizationTable 경유로 오인해 UI 문구 우회가 통과한다 | `Other:FormatByKey("goal.signal_2")`가 `i18n.hardcoded_text`·`i18n.missing_key` 모두 빈 결과 | 수신 객체를 신뢰된 Text/translator 경로로 제한하고 미확인 수신자는 거부

major | harness/checks/i18n.py:262-264 | 데이터 모델 UI 속성에 Localization 키를 직접 넣어도 통과한다 | `Text = "goal.signal_2"`인 `TextLabel`이 `i18n.hardcoded_text`에서 검출되지 않음 | 데이터 모델의 UI 문구 속성은 키 여부와 무관하게 거부하거나 명시적 런타임 바인딩만 허용

major | harness/checks/safety.py:103-115; harness/checks/server.py:151-158 | `grant` 인자의 모든 문자열을 URL 검사에서 제외해 도메인형 보상 ID가 통과한다 | `RewardService.grant(player, "evil.museum", "m.gate_open")`에서 `safety.url`·`server.duplicate_reward` 모두 빈 결과 | 허용된 보상/미션 ID만 예외 처리하고 미등록 ID의 도메인은 URL로 거부

major | harness/checks/server.py:28-30,151-157,653-657 | 함수값으로 넘긴 보상 호출을 추적하지 않아 판정 없는 보상이 통과한다 | `pcall(RewardService.grant, player, "reward.explorer_card", "m.gate_open")`가 `server.duplicate_reward`·`server.reward_after_verdict` 모두 빈 결과 | 호출식이 아닌 trusted module 멤버 참조도 추적하거나, 고차 함수 인자로 넘긴 미해석 함수는 거부

major | harness/checks/analytics.py:227-252 | 함수값으로 넘긴 분석 전송을 검사하지 않아 허용 밖 이벤트가 통과한다 | `pcall(Analytics.log, player, "not_allowed", {})`가 `analytics.calls`에서 검출되지 않음 | 분석 sender 멤버의 고차 함수 전달·호출 경로를 추적하거나 미해석 전달을 거부

major | harness/checks/server.py:553-558,574-580 | table 원격 입력의 중첩 필드 범위를 계약과 비교하지 않는다 | 계약 `payload.x: -2..2`에 코드 가드 `-9999..9999`를 둬도 `server.remote_validation`이 빈 결과 | 중첩 `fields`에도 canonical/min/max를 검증하고 코드 가드와 정확히 대조
