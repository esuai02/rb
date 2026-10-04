GOAL: rb 저장소 작업 Graph 단계 Q1(의도 명세 고정)의 산출물이 합격 기준과 Intent 불변식을 실제로 만족하는지 독립적으로 검토한다. 단계 결과: 월드 하나의 의도(월드 역할·대상 연령·성숙도 설문 예상 답·시장 결정 방식·번역 금지 구간 포함)가 기계가 읽는 명세로 고정되고 원본 월드 1개가 채워진다.
SCOPE: 산출물 파일 specs/templates/world-intent.schema.json, specs/worlds/neo-seoul-city-language-gate.yaml, tools/validate_spec.py, tests/test_validate_spec.py (저장소 루트 기준). 계약은 graph.json 의 Q1 노드, 불변식은 intent.md §5(INV-1~16), 용어는 intent.md §0.
INVARIANTS: 수정하지 말 것(읽기 전용). 합격 기준:
- Q1-C1: 명세 형식이 필수 항목을 모두 요구한다 (목표: 빠진 항목마다 실패, 완전한 명세는 통과)
- Q1-C2: 도시 언어 게이트 원본 명세가 검사를 통과하고, 성숙도 설문 예상 답이 16세 이상 항목(소셜 행아웃·자유 창작·민감 이슈·확장 AI 상호작용·유료 랜덤·유료 거래)에 모두 '아니오'다 (INV-16) — 금지어 용어집 파일의 존재와 내용은 Q2-C5 에서 검사한다(Q1 은 시장과 맞는 경로만) (목표: 통과, 6항목 모두 아니오)
- Q1-C3: 언어·시장·교육과정 키가 나뉜다: locale 은 BCP-47, market 은 지역 포함, 엔진은 시장 중립 grade_band 만 쓴다 (INV-3) (목표: 섞인 키 실패, 올바른 키 통과)
- Q1-C4: B안 언어 우선 필드가 있다: 용어마다 일상 표현·행동·이름표 순서와 재사용 맥락 자리 (INV-15) (목표: 필드 누락 시 실패)
- Q1-6V: 이 단계를 잠그기 전에 6방향(전방·후방·위·아래·좌·우) 검토가 이 단계를 대상으로 기록된다 (intent §11) (목표: 6방향 각 1건 이상)
EVIDENCE: 자동 검사 결과(binding 9c3b4caa40a3):
- Q1-C1: PASS — exit 0; OK
- Q1-C2: PASS — exit 0; OK
- Q1-C3: PASS — exit 0; OK
- Q1-C4: PASS — exit 0; OK
- Q1-6V: PASS — 6방향 모두 기록됨
STAGE SCOPE: 이 단계가 맡는 불변식: INV-3 키 분리, INV-9 협동 선택·입력 3종(명세 칸), INV-15 언어 우선 순서(명세 칸), INV-16 성숙도 설문·안전 플래그, DEC-9 대상·성숙도
다음 단계로 넘긴 것(이 단계의 결함이 아니다 — 넘긴 단계의 기준이 검사한다):
- INV-10 개인정보·분석 이벤트 → Q2-C3 · Q3-C1
- INV-11 금지어 용어집 파일·내용 → Q2-C5
- INV-15 재사용 맥락 3개 이상 → Q2-C2
- INV-4·INV-12 서버 권위·무작위 보상(코드) → Q3-C1
- INV-16 코드 수준(런타임 LLM·URL·필터 없는 텍스트) → Q3-C1
ASK: 각 합격 기준이 실제로 참인지, 테스트가 기준이 말하는 것을 정말로 검사하는지(빈 검사·우회 가능한 검사 포함), 이 단계가 맡는 불변식을 산출물이 어기는지 찾아라. 넘긴 항목은 지적하지 말고, 넘긴 단계의 기준으로 덮이지 않는 빈틈만 지적하라. 추측은 근거와 함께만.
RETURN: lines of `severity | file:line | claim | evidence | minimal fix` (severity = critical|major|minor), or exactly NO_FINDINGS
