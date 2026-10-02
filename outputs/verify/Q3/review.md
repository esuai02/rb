major | harness/checks/i18n.py:145-153 | 승인된 문구 함수가 아닌 함수가 만든 UI 문구를 통과시킨다 | `goal.Text = getText("label")`은 문자열이 식별자형이라 `hardcoded_text`와 `unresolved_ui_text` 모두 빈 결과가 된다 | UI 대입 RHS는 `Text.get` 등 허용된 키 호출·해석 가능한 상수 외 호출을 거부

major | harness/checks/analytics.py:90-105,131-136 | 분석 모듈이 조립한 이벤트명을 통과시킨다 | `eventName .. "_bad"`를 `LogCustomEvent`에 넣어도 `_computed`가 함수 호출만 인식해 결과가 빈 목록이다 | 이벤트 인자는 허용된 리터럴·매개변수 외 모든 식을 미해석으로 거부

major | harness/run.py:106-120 | 재실행 시 검사 수와 기록 파일 수가 달라질 수 있다 | 기존 `out`의 오래된 기록을 제거·검증하지 않고 현재 검사 파일만 덮어쓴다 | 실행별 새 기록 디렉터리를 사용하거나 현재 검사 ID 밖의 기존 기록을 실패 처리·정리하고 이를 테스트

major | tests/test_harness.py:189-192,220-223 | Q3-C1의 “의도한 진단 문구”를 검증하지 않는다 | 테스트는 결함별 검사 ID 집합만 비교하며 메시지 내용은 일부 별도 분기 테스트에만 있다 | 각 결함에 기대 진단 fragment/코드와 금지 진단을 매니페스트·독립 표에 두고 결함 114종 모두 검증

minor | tests/test_harness.py:28-31,213-215 | Q3-C1 기준과의 결함 종류 연결 검사가 114종 전체가 아니라 20종만 확인한다 | `REQUIRED_CLASSES`만 그래프 문장에 포함됐는지 검사하며 나머지 94종은 기준 문장과의 연결을 검증하지 않는다 | 114개 결함 class/ID 전체를 기준 데이터로 고정해 Q3-C1 문장 또는 별도 기준표와 전수 대조
