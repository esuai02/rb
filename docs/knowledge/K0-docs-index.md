# K0 원천 문서 목록·충돌 정리

- 만든 방법: 2026-10-01, 읽기 전용 하위 에이전트 4개가 `docs/` 원천 문서 17건을 모두 읽고 `intent.md`·K1~K5 와 대조했다(근거 `evidence.jsonl` I1). `docs/readme.md` 의 재구성 1단계(분류)·2단계(충돌 표시)에 해당한다.
- 성격: 색인이다. 원천 문서는 고치지 않았다. 충돌의 해결은 `intent.md` 의 DEC·INV 와 `decisions.md` 가 한다.
- 성격 표기: 원칙 = 헌법 후보 · 패턴 = 재사용 설계 · 명세 = 월드 기획값 · 검사 = Harness 규칙 · 혼합 · 아이디어

## 1. 원천 문서 17건

| # | 파일 (`docs/`) | 성격 | 내용 | readme 재구성안의 위치 |
|---|---|---|---|---|
| 1 | 00-도시언어 게이트 통과 게임 | 혼합 | 입국심사 → "도시 언어 게이트". 수학 = 도시의 협동 언어. 언어 친숙화 지표·북극성·MVP 0.1/0.2/1.0 | constitution(헌장) · patterns/onboarding · ADR-001·002 |
| 2 | 목적이 수학학습이 아니라 수학용어를 일상어처럼 사용하도록 익숙해지 | 원칙 | 목표를 "수학 용어를 생활 언어처럼 자발적으로 고르고 다시 쓰기"로 다시 고정. 게이트·피드백·성장·지표·AI 생성 규칙 재정의 | constitution(헌장·언어 우선 교수법) · ADR-001 |
| 3 | 수학적 언어의 일상화 | 혼합 | 제목과 달리 내용은 온보딩: 도시 언어 게이트 첫 5분 시간표·Prompt 배치·지연 힌트·서버 상태 머신·퍼널·MVP | patterns/onboarding/city-language-gate |
| 4 | 수학적 언어를 즐겨 쓰게 만드는 인터페이스의 핵심 | 패턴 | "도시 소통 UI": 표현 선택 → 월드 반응 → 언어 발견 → 재사용. 화면 6개·현지화 키·QA L01~L14 | patterns/language(expression-wheel 등) |
| 5 | 수학 학습 게임에서 과정 지향 피드백을 UI로 구현하는 법 | 패턴 | 관찰→해석→다음 행동→재시도 4단 피드백, 힌트 Level 0~4, QA F01~F13 | patterns/gameplay/process-feedback · ui-ux/feedback-card |
| 6 | 수학마을 탐험 게이트 온보딩 상세 기획서 | 명세 | 5분 온보딩 상태 그래프·신호 1~3·협동 3모드·이벤트 27개·퍼널 합격선·A/B·QA T01~T12·U01~U08·M01~M07·서비스 구조 | specs/worlds/neo-seoul-central-gate · harness/test-scenarios |
| 7 | 첫 5분의 재미를 검증하고 이후 장기 루프를 만드는 장치 | 아이디어 | 아이디어 10개(도시가 기억함·안전한 첫 실패·오개념 = 도시 이상현상 …)와 MVP 축소안 | patterns/gameplay (Q5 뒤 백로그) |
| 8 | 로블록스 게임 내 온보딩 튜토리얼 UX 디자인 팁 | 패턴 | 협동 튜토리얼: 혼자 완주 보장·역할 교대·대기 마찰 제거·비난 없는 피드백·공정 보상·채팅 없는 협동·자동 테스트 7개 | patterns/onboarding/solo-safe-coop |
| 9 | 수학마을이 … 살아 있는 도시처럼 … AI Factory 가 … 가드레일 | 혼합 | 장기 루프(시민 의뢰 게시판·공동 복구 지도·탐험 지도책·역할 교대·단계적 UGC) + AI 수정 권한 3단계·교육 훼손 금지 Hard Gate | patterns/gameplay (Q5 뒤) · constitution(가드레일) |
| 10 | 도시의 신호를 복구하고 다음 실험으로 나아가는 행동 | 혼합 | 제목과 달리 ProximityPrompt 설계: 오브젝트별 분류·속성값·전역 서버 라우터·Custom UI 시점·QA P01~P14 | patterns/ui-ux/custom-proximity-prompt · reference/roblox |
| 11 | 플레이어가 다음 실험을 실행하도록 월드의 조절 장치와 연결해 주는 인터페이스 | 혼합 | 제목과 달리 서버 권위 동적 피드백 구현: FeedbackPayload 계약·힌트 단계·우선순위 큐·QA D01~D13 | patterns/technical · harness/ux/feedback-rules |
| 12 | 로블록스 로컬라이제이션 테이블 활용법과 언어별 길이 대응 | 혼합 | LocalizationTable 키 설계(용어·일상어 행동·피드백 분리)·FormatByKey·늘어나는 UI·RTL·CJK·QA LOC01~LOC10 | patterns/ui-ux/localization-resilient-ui · reference/localization (K1 과 합침) |
| 13 | ProximityPrompt 커스텀 UI 제작 방법 (Style = Custom) | 패턴 | Style=Custom Prompt 직접 구현과 서버 검증, 협동 프리즘 스위치 예시 | patterns/ui-ux/custom-proximity-prompt |
| 14 | ProximityPrompt 커스텀 UI 제작 방법 | 패턴 | 13 의 마크다운 이스케이프 변형본 + 경사 콘솔 예시 | 13 과 합치고 한쪽 폐기 |
| 15 | ProximityPromptService 전역 이벤트 | 패턴 | 클라이언트 UI 컨트롤러 1개 + 서버 라우터 1개(InteractionId → Handler) 구조 | patterns/technical/prompt-global-router |
| 16 | ProximityPrompt 다중 조건 검증 최적화 | 검사 | 서버 검증 파이프라인(싼 검사 → 비싼 검사)·PromptValidator·멱등 보상·QA V01~ | harness/technical/prompt-security · reward-idempotency |
| 17 | HoldDuration 홀드 게이지 Tween 애니메이션 구현 | 패턴 | 홀드 게이지 모듈·모바일 터치 홀드·협동 홀드·QA H01~H12 | patterns/ui-ux/hold-gauge |

별도: `docs/readme.md` = 재구성 설계안 자체(DEC-13). `docs/01-…guide.md`·`02-start-here.md` = 연결 문서.

## 2. Intent 와의 충돌 — 어디에 반영했나

| 충돌 | 문서 | 반영 |
|---|---|---|
| **제품 목적**: "수학 학습 게임" ↔ "수학 언어 친숙화 글로벌 소셜 어드벤처, 북극성 = 주간 도시 언어 재사용" | 1·2·3·4·12·readme (9 는 중간) | intent §1 A/B안, **DEC-10** |
| 언어 우선 규칙 추가 후보: 정의보다 행동 먼저 · 용어는 행동 뒤 이름표 · 일상어로 항상 진행 가능 · 같은 용어 3개 맥락 재사용 · 정답률 단독 지표 폐기 | 1·2·4 | DEC-10 이 B안이면 INV 로 올린다 |
| 수학 용어를 언어 키(LocalizationTable)에 둠 ↔ 용어 이름은 시장 축 | 4·12 | intent §4, Q2 에서 키 체계 결정 |
| 장기 구조(시민권·Metro District·의뢰 게시판·자격 게시판)를 첫 MVP 에 넣음 | 1·6·7·9·10·13·14·15·16 | INV-2 유지(Q5 뒤), §10 후보 C |
| 다국어·Harness 를 MVP 1.0 으로 미룸 ↔ 처음부터 키 분리·Harness 먼저 | 1·3·7 | INV-1·INV-3 유지 |
| 플레이어별 진단·용어 사용 기록 저장 전제 | 2·5·6·7·11·16 | **DEC-12** |
| 기본 보상: 기여 기준 ↔ 완주자 동일 + 소규모 협동 보너스 | 8 ↔ K3 | INV-4 를 "기본 보상 동일, 협동 보너스만 기여 기준"으로 정리 |
| 협동 의뢰 2~4명 조건 → 혼자 온 플레이어 배제 | 9 | INV-9 유지 |
| AI 수정 권한 Green 등급(사후 검토) ↔ 라이브 변경은 사람 승인 먼저 | 9 | INV-13 유지(스테이징 안에서만 자동) |
| 추가 금지 후보: 국가·언어·학년별 보상 차등 · 개인 학습 결과 타인 공개 · 무료 학습 경로 축소 · 강한 FOMO · UGC 1단계 자유 텍스트 | 9 | 헌법(DEC-13) 또는 INV 추가 후보 — 사람 판단 |
| 클라이언트 코드에 한국어 문구 리터럴 | 13·14·15·17 | INV-3 위반 예시 — 패턴으로 옮길 때 키로 바꾼다 |
| 자격 부족 "잠김 안내"(대안 경로 없음) | 16 | INV-8 — 다음 행동을 함께 보이게 |

## 3. 문서 간 충돌 — Q2 에서 정본 값 하나로 정할 것

| 항목 | 문서별 값 |
|---|---|
| 게이트 이름 — **정본: 도시 언어 게이트 (DEC-1, 2026-10-01)** | 수학마을 입국심사(원래 말) · 수학마을 탐험 게이트 / Math Village Arrival Gate(6·7·8, K2) · 도시 언어 게이트 / 도시 언어 심사(1·3) · 도시 신호 언어 게이트 / Math Village Signal Gate(2) · 도시 언어 등록 게이트(3) · Seoul Signal Gate(6, 오브젝트) · City Language Gate(readme 제안 ADR-002) |
| 세계·칭호 — **세계 이름 정본: Neo Seoul (DEC-1)**, 칭호는 Q2 | Neo Seoul · Neo Seoul Central · 사이버 서울 · 서울 사이버 시민권 · Seoul Cyber Citizen Badge · Neo Seoul 시민 명예 타이틀 · Neo Seoul Master Explorer(9) |
| 첫 보상·수집 | 탐험 카드 + 시민 견습 배지 Lv1 + 이동 부스터(6) · 도시 언어 탐험가 배지·탐험 지도책(1) · City Language Atlas(2) · City Signal Atlas(4·9) |
| 게이트 신호 구성 | 위치·변화·나눔(1·2) · 신호1 상호작용 → 신호2 좌표 → 신호3 협동 스위치(6) · 첫 신호·위치·변화 + 협동(3) · 좌표·변화율·패턴(K2) · MVP 0.1 = 좌표 하나(1·7) |
| 게이트 시간 | 3~5분, 7분 넘으면 경고(6) · 3분(7) · 3분 안·3~5분(8, 문서 안에서도 다름) · readme 예시 Metro 8분 |
| 매칭 대기 상한 | 10초(6·readme) · 10~15초(1·8) · 15초 타임아웃(8 자동 테스트) |
| 협동 동시 판정 창 | 3초(6) · 2~4초(8) |
| 서버 거리 허용치 | 8(16 매트릭스) · 10(13·14) · 12(15) · 14·20(10·11) studs |
| 서버 쿨다운 | 0.35(15·16) · 0.5(16 매트릭스·17) · 0.6/0.7·1.2/1.5(16 예시끼리 다름) |
| 홀드 시간 | 0.4~0.8 / 0.5 / 0.6초(10 안에서도 다름) · 협동 스위치 0.4~0.8(3) |
| 홀드 취소 | 즉시 0(13) · 0.12초 Tween(14·15·17) · H05 0.2초 허용 |
| 변화 신호 선택지 | [더 올라가게][그대로][더 내려가게](3) · [더 올라가게][평평하게][더 내려가게](4) — "그대로"와 "평평하게"(기울기 0)는 수학적으로 다르다 |
| 좌표 표현 | "오른쪽 2, 위 1"(1) · "오른쪽 2, 앞으로 1칸"(6) · 숫자 "(3, -2)"(8) · 표현 휠 [오른쪽 2][위로 1](2) · 방향 → 거리 두 단계(4) |
| 힌트 강화 기준 | 5·10·15·25초(6) · 실패 2회째 정답 위치 점멸(3) · Level 0~4, 정답 보기는 마지막만(5) · 3회 실패 시 상승 vs 매 실패 +1(11 안에서 다름) · 무접근 15초 → +10초(10) |
| 발견 태그 노출 | 1~2초(2) · 2초 뒤 축소, L06 2~4초(4) · 피드백 카드 2~4초(5) |
| 이벤트 이름·수 | 27개(6) · 10개(7) · session_start·explorer_card_earned(K5) ↔ ftue_started·explorer_card_granted(3) |
| 협동 스위치 식별자 | gate_prism_left(13·14) ↔ prism_left_ready(15·16), 함수 이름도 다름 |
| 규칙 정본 위치 | Prompt Attribute(15) ↔ 서버 Config, Prompt 는 표시용(16) |
| 보조 NPC | 루미(1·6·15) · 라인 드론(6) · 보조 드론(17) |
| 친구 협동 제안 시점 | 첫 게이트 신호 3(6·8) ↔ 첫 자격 획득 뒤에만(7) |
| 첫 시도 설계 | 첫 시도 성공률을 주요 지표로(6) ↔ 모두 한 번은 "안전한 실패"를 겪게(7) |
| 색 의미 | 홀드 중단 = 보라/회색(17) ↔ K4 보라 = 특별 미션·시민권 |

## 4. 정리 대상 파일 (지우지 않음 — 사용자 판단)

- `blank.md`, `blank - 복사본 (10)~(27).md`: 19개, 내용은 공백 한 칸. 붙여 넣기 틀로 보인다.
- `blank - 복사본 (2).md`: `ProximityPromptService 전역 이벤트.md` 와 바이트 단위로 같다.
- 14 는 13 의 변형본이다.

## 5. readme 재구성안 ↔ 지금 구조 (DEC-13 판단 자료)

| readme 층 | 지금 있는 것 | 채택하면 |
|---|---|---|
| `wiki/00-constitution` (헌장·금지·안전·교수법·용어집) | intent.md §1·§5 | 제품 규칙 정본을 옮기고 intent.md 는 순서·결정·Q 만 남긴다 (정본 하나 유지) |
| `wiki/10-patterns` | 원천 문서 4·5·8·10~17 | 문서별로 "Intent–Mechanic–Guardrail–Test" 형식으로 변환 |
| `wiki/20-reference` | K1~K5, 공식 문서 사실 F1~F6 | 옮기기만 하면 된다 |
| `wiki/30-decisions` (ADR) | decisions.md + evidence.jsonl | 결정됨이 된 DEC 마다 ADR 1개 |
| `specs/` | 없음 (Q1·Q2 산출물) | 작업 Graph 생긴 뒤 만든다 (W2 가 그 전 생성을 막는다) |
| `harness/` | 없음 (Q3 산출물) | 위 §1 의 QA 묶음(T·U·M·L·F·P·D·LOC·V·H·K4 U)을 하나의 ID 체계로 합친다 — 겹침: P12≈D09≈U2, P13≈D10≈LOC03≈U7, P04≈U6, P07≈D11≈D13 |
| `src/`·`tests/` | 없음 (Q4 산출물) | 〃 |
