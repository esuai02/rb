critical | tests/test_harness.py:320-323 | `RB_FREEZE_DIAGNOSES=1`이면 진단 스냅샷 검증이 아니라 현재 결과를 덮어쓰고 건너뛴다 | 환경변수 분기에서 `DIAGNOSES.write_text(...)` 후 `skipTest`한다 | 스냅샷 갱신을 일반 테스트에서 제거하고 별도 명시적 도구로 분리

major | harness/source.py:117-125 | 중첩된 잘못된 Rojo 트리 구조를 조용히 무시해 통과시킨다 | `_mappings`가 dict가 아닌 자식을 `continue`하며 오류를 기록하지 않는다 | 모든 비 `$` 자식이 객체인지 재귀 검증하고 아니면 `tree.problems`에 기록

major | harness/checks/safety.py:10,55-62 | 허용 목록 밖의 bare domain URL을 놓친다 | URL 정규식의 도메인 TLD가 제한되어 `example.education`·`example.ai` 등을 검출하지 못한다 | 일반적인 hostname/URL 패턴을 보수적으로 거부하거나 명시적 허용목록을 둔다

major | harness/checks/i18n.py:14,238-239 | 식별자처럼 보이는 하드코딩 화면 문구를 전역적으로 제외한다 | `"Ready"` 같은 문자열은 `IDENTIFIER.fullmatch` 때문에 `hardcoded_text`에서 무시된다 | 문자열 허용을 호출·속성 문맥별로 제한하고 미확인 문자열은 거부

major | harness/checks/analytics.py:184-203 | 분석 플랫폼 필드를 계산된 표 키로 만들면 `analytics.calls`가 검사하지 않는다 | 검사 대상이 문자열 대괄호 대입·점 대입뿐이며 `{[dynamicKey] = value}` 표 리터럴은 빠진다 | 플랫폼 전송 표의 모든 computed key를 분석하거나 해석 불가 시 거부

minor | tests/test_harness.py:526-540 | Q3-C4 테스트가 mode와 stage의 올바른 대응을 검증하지 않는다 | `static` 외에는 stage가 단순히 `Q2~Q8`인지와 `covered_by`만 확인한다 | `static→Q3`, `runtime/static_later→Q4`, `human→Q8`, `covered→Q2` 매핑을 단정적으로 검사
