가능합니다. 지금 만든 파일들을 단순 문서 모음으로 두지 말고, \*\*LLM이 읽는 지식베이스 + 기계가 검증하는 명세 + 에이전트가 실행하는 작업 그래프\*\*로 재구성하면 Roblox 게임 제작 자동화의 운영체제가 됩니다.



핵심은 모든 문서를 한 거대한 위키에 합치는 것이 아닙니다.  

\*\*변하지 않는 원칙\*\*, \*\*재사용 가능한 설계 패턴\*\*, \*\*게임별 설정값\*\*, \*\*자동 검증 규칙\*\*, \*\*실행 절차\*\*를 분리해야 LLM이 헷갈리지 않고 자동화가 가능합니다.



&#x20;



\## 목표 구조



최종적으로는 Claude Code 같은 에이전트가 아래처럼 동작하게 만드는 것이 목표입니다.



```text

새 월드 요청

&#x20; ↓

LLM Wiki에서 불변 원칙·패턴·용어·안전 규칙 검색

&#x20; ↓

Intent Spec 생성

&#x20; ↓

Curriculum / Quest / World Graph 생성

&#x20; ↓

Roblox Luau·UI·월드 설정 코드 생성

&#x20; ↓

Harness 규칙으로 자동 테스트

&#x20; ↓

실패 원인 분석·수정

&#x20; ↓

Studio MCP로 스테이징 Place 반영

&#x20; ↓

사람이 Play / Revise / Reject

```



예를 들면 당신이 이렇게 요청합니다.



```text

Neo Seoul의 Metro District 월드를 생성해.

대상은 글로벌 9\~14세.

목표는 수학 실력 측정이 아니라

‘기울기’라는 수학 언어를 일상어처럼 쓰게 하는 것.

레이싱·협동 장르.

모바일 우선.

플레이 시간 8분.

친구가 없으면 NPC 드론이 대체해야 함.

```



에이전트는 Wiki에서 다음을 자동으로 찾아야 합니다.



```text

\- 제품 헌장: 수학 언어 친숙화가 목적

\- 금지 규칙: 시험/정답/불합격 중심 구조 금지

\- 한국 세계관: Neo Seoul Design System

\- 기울기 언어 패턴: “더 올라가게” → “기울기”

\- 협동 설계: 친구 없이도 NPC로 완주 가능

\- UI 규격: 모바일, 2\~4개 선택지, 긴 텍스트 금지

\- Prompt 규격: 서버 검증, Custom UI 사용 조건

\- 보안 Harness: 거리·상태·쿨다운·멱등 보상

\- 현지화 규격: LocalizationTable 키와 언어 길이 대응

```



이 자료를 찾지 못하면 LLM은 매번 새로 추측하고, 결국 “수학 문제를 푸는 3D 퀴즈 게임”으로 회귀합니다.



\*\*\*



\## Wiki의 네 계층



\### 1. Constitution: 절대 바꾸면 안 되는 원칙



가장 먼저 한 파일로 고정해야 하는 부분입니다. 모든 생성·리뷰 에이전트가 작업 전에 읽어야 합니다.



```text

wiki/00-constitution/

&#x20; product-charter.md

&#x20; non-negotiables.md

&#x20; safety-policy.md

&#x20; pedagogy-language-first.md

&#x20; glossary.md

```



\### `product-charter.md` 예시



```md

\# Product Charter



\## Product purpose



This product does not primarily optimize for:

\- test scores

\- speed of calculation

\- ranking students by math ability

\- forcing mathematical terminology



This product optimizes for:

\- familiarity with mathematical language

\- voluntary reuse of mathematical terms in meaningful contexts

\- collaborative communication using location, change, relation, and pattern language

\- a feeling that mathematical language is useful and ordinary



\## Core player fantasy



The player is not a student taking a test.



The player is a city explorer who helps Neo Seoul understand and restore

its signals through the language of position, change, relation, and pattern.



\## Non-negotiable design rule



Every mathematical term must follow this sequence:



situation

→ everyday expression

→ player action

→ world response

→ mathematical label

→ reuse in a different situation



Never begin with a definition, flashcard, or multiple-choice test.

```



이 파일은 게임 기획서가 아니라, 모든 LLM의 판단을 제한하는 \*\*헌법\*\*입니다.



\### `non-negotiables.md` 예시



```md

\# Non-Negotiables



\## The game must not



\- block progress because a player does not know a mathematical term

\- use "wrong answer", "fail", "rejected", or "not qualified" as primary feedback

\- require friends to complete onboarding

\- require real-world location, school, age, contact information, or external accounts

\- represent real immigration, nationality, visas, borders, or legal citizenship

\- gate learning retries or hints behind Robux payments

\- publicly rank mathematical language use or inferred ability

\- use free-text communication as a requirement for collaboration



\## The game must



\- allow everyday language and mathematical language to coexist

\- permit solo completion through NPC assistance

\- use server-authoritative progress and reward validation

\- support small mobile screens before desktop polish

\- localize terms with curriculum-aware review

```



이 파일이 없으면 AI가 성장률을 높이겠다고 “정답을 못 맞히면 게이트 통과 불가” 같은 시스템을 다시 만들 수 있습니다.



\*\*\*



\### 2. Patterns: 재사용 가능한 게임 설계 패턴



여기에는 대화에서 만든 좋은 아이디어를 “한 번 쓰고 끝나는 기획서”가 아니라, 다른 월드에 재사용할 수 있는 패턴으로 정리합니다.



```text

wiki/10-patterns/

&#x20; onboarding/

&#x20;   city-language-gate.md

&#x20;   first-5-minutes.md

&#x20;   delayed-hints.md

&#x20;   solo-safe-coop.md



&#x20; language/

&#x20;   everyday-to-math-term.md

&#x20;   language-discovery-tag.md

&#x20;   expression-wheel.md

&#x20;   team-language-pings.md

&#x20;   language-reuse-loop.md



&#x20; gameplay/

&#x20;   city-request-board.md

&#x20;   cooperative-role-rotation.md

&#x20;   city-restoration.md

&#x20;   language-credential.md

&#x20;   process-feedback.md



&#x20; ui-ux/

&#x20;   mobile-hud.md

&#x20;   feedback-card.md

&#x20;   custom-proximity-prompt.md

&#x20;   hold-gauge.md

&#x20;   localization-resilient-ui.md



&#x20; safety/

&#x20;   fictional-gate-not-immigration.md

&#x20;   child-safe-cooperation.md

&#x20;   no-free-text-dependency.md

```



\### `everyday-to-math-term.md` 예시



```md

\# Pattern: Everyday Expression to Mathematical Term



\## Intent



Help players become familiar with mathematical language without requiring

memorization or prior mastery.



\## Required sequence



1\. Present a meaningful world situation.

2\. Offer an everyday expression that describes an action.

3\. Let the player act.

4\. Show a visible world result.

5\. Attach the mathematical name after the action.

6\. Reuse the same term in a different world context.



\## Example: slope



Situation:

A train path arrives below the target platform.



Everyday expression:

"Make the path rise more."



Player action:

Adjust the rail slope.



World response:

The train reaches a higher platform.



Mathematical label:

"The city calls how a path rises or falls a slope."



Reuse:

Use slope language later for a drone route, water flow, or sky rail.



\## Acceptance criteria



\- No definition appears before player action.

\- The player can complete the mission using everyday language.

\- Mathematical terminology is attached after a visible consequence.

\- The term appears meaningfully in at least three distinct contexts.

\- Feedback describes result and next action, not student ability.

```



\### `solo-safe-coop.md` 예시



```md

\# Pattern: Solo-Safe Cooperative Mission



\## Rule



Co-op enriches the experience but never blocks first-session progress.



\## Modes



\- Friend present: asymmetric collaborative roles

\- Matchmaking selected: wait at most 10 seconds

\- No teammate: NPC assistant immediately fills missing role

\- Teammate leaves: NPC substitutes without resetting progress



\## Allowed rewards



\- extra visual spectacle

\- team trust

\- optional route

\- social cosmetic

\- collective city contribution



\## Forbidden rewards



\- core progression only for groups

\- mathematical language access only for groups

\- strong power advantage

\- public penalty for solo players

```



\*\*\*



\### 3. Specs: 월드별로 바뀌는 설정값



이 층은 LLM이 직접 편집해도 되는 부분입니다. 게임 전체 원칙은 건드리지 않고, 새로운 월드·학년·언어·장르를 Config로 추가합니다.



```text

specs/

&#x20; worlds/

&#x20;   neo-seoul-central-gate.yaml

&#x20;   metro-district.yaml

&#x20;   pattern-palace.yaml

&#x20;   han-river-dock.yaml



&#x20; curriculum-packs/

&#x20;   ko-KR/

&#x20;     middle-2-linear-language.yaml

&#x20;   en-US/

&#x20;     linear-relationships-language.yaml

&#x20;   ja-JP/

&#x20;     linear-functions-language.yaml



&#x20; localization/

&#x20;   terms/

&#x20;     ko-KR.yaml

&#x20;     en-US.yaml

&#x20;     ja-JP.yaml

&#x20;   ui/

&#x20;     common.csv

&#x20;     gate.csv

&#x20;     metro.csv



&#x20; experiments/

&#x20;   onboarding-hint-delay.yaml

&#x20;   expression-wheel-order.yaml

```



\### 월드 Spec 예시



```yaml

\# specs/worlds/metro-district.yaml



id: metro\_district\_v1

title\_key: world.metro.title



world\_identity:

&#x20; region: neo\_seoul

&#x20; theme: future\_transit

&#x20; visual\_palette:

&#x20;   primary: teal

&#x20;   accent: gold

&#x20;   night: purple



audience:

&#x20; age\_band: "9-14"

&#x20; priority\_platform: mobile

&#x20; session\_minutes: 8

&#x20; players: "1-4"



core\_fantasy:

&#x20; "Restore a broken metro line by helping the city understand

&#x20; how paths rise, fall, and connect."



language\_goal:

&#x20; concept\_id: slope

&#x20; everyday\_expressions:

&#x20;   - action.slope.increase

&#x20;   - action.slope.decrease

&#x20;   - action.slope.level

&#x20; mathematical\_terms:

&#x20;   - term.slope.name

&#x20;   - term.slope.positive

&#x20;   - term.slope.negative

&#x20; required\_reuse\_contexts:

&#x20;   - rail\_path

&#x20;   - drone\_route

&#x20;   - energy\_flow



gameplay:

&#x20; genre:

&#x20;   - co\_op\_racing

&#x20;   - route\_building

&#x20; missions:

&#x20;   - id: rail\_signal\_repair

&#x20;     duration\_minutes: 3

&#x20;     language\_action: action.slope.increase

&#x20;     math\_label\_after\_action: term.slope.name

&#x20;   - id: skyrail\_route

&#x20;     duration\_minutes: 3

&#x20;     language\_action: action.slope.decrease

&#x20;     math\_label\_after\_action: term.slope.negative



co\_op:

&#x20; friend\_bonus: visual\_route

&#x20; npc\_fallback: line\_drone

&#x20; matchmaking\_wait\_seconds: 10

&#x20; mandatory\_co\_op: false



rewards:

&#x20; core:

&#x20;   - city\_language\_atlas.slope

&#x20;   - unlock.metro\_booster

&#x20; optional:

&#x20;   - cosmetic.metro\_signal\_badge



forbidden:

&#x20; - multiple\_choice\_quiz\_loop

&#x20; - mandatory\_math\_definition

&#x20; - public\_skill\_ranking

&#x20; - paid\_hints

```



이런 YAML 파일 하나가 AI에게 “Metro District를 어떻게 만들어야 하는지”를 구조적으로 전달합니다.



\*\*\*



\### 4. Harness: 자동 생성물의 통과 기준



Wiki만 만들면 에이전트는 문서를 읽고 그럴듯한 게임을 만들지만, 품질을 자동으로 보장하지 못합니다. 따라서 모든 월드는 Harness를 통과해야 합니다.



```text

harness/

&#x20; product/

&#x20;   charter-rules.yaml

&#x20;   language-first-rules.yaml

&#x20;   child-safety-rules.yaml



&#x20; curriculum/

&#x20;   term-context-validation.yaml

&#x20;   everyday-to-term-validation.yaml

&#x20;   misconception-rules.yaml



&#x20; ux/

&#x20;   mobile-layout-rules.yaml

&#x20;   onboarding-rules.yaml

&#x20;   feedback-rules.yaml

&#x20;   coop-rules.yaml



&#x20; technical/

&#x20;   prompt-security-rules.yaml

&#x20;   reward-idempotency-rules.yaml

&#x20;   remote-validation-rules.yaml

&#x20;   localization-rules.yaml



&#x20; test-scenarios/

&#x20;   gate-solo.yaml

&#x20;   gate-two-player.yaml

&#x20;   prompt-exploit.yaml

&#x20;   small-mobile-ui.yaml

&#x20;   long-translation-ui.yaml

```



\### `language-first-rules.yaml` 예시



```yaml

rules:

&#x20; - id: LF-001

&#x20;   severity: blocker

&#x20;   description: "A mathematical term must not be defined before a player action."

&#x20;   evidence\_required:

&#x20;     - mission\_flow

&#x20;     - localized\_text\_order



&#x20; - id: LF-002

&#x20;   severity: blocker

&#x20;   description: "Core progress must be possible using everyday language."

&#x20;   evidence\_required:

&#x20;     - alternate\_expression\_path

&#x20;     - solo\_playtest



&#x20; - id: LF-003

&#x20;   severity: blocker

&#x20;   description: "No mission may use wrong-answer or pass/fail language as primary feedback."

&#x20;   banned\_patterns:

&#x20;     - "오답"

&#x20;     - "불합격"

&#x20;     - "입국 거부"

&#x20;     - "wrong answer"

&#x20;     - "rejected"



&#x20; - id: LF-004

&#x20;   severity: warning

&#x20;   description: "Each term should appear in at least three distinct game contexts."

&#x20;   minimum\_contexts: 3



&#x20; - id: LF-005

&#x20;   severity: blocker

&#x20;   description: "A player must not be publicly ranked by inferred mathematical ability."

```



\### `prompt-security-rules.yaml` 예시



```yaml

rules:

&#x20; - id: SEC-PP-001

&#x20;   severity: blocker

&#x20;   description: "Prompt-triggered rewards must be validated on the server."



&#x20; - id: SEC-PP-002

&#x20;   severity: blocker

&#x20;   description: "Every reward must be idempotent."



&#x20; - id: SEC-PP-003

&#x20;   severity: blocker

&#x20;   description: "Prompt interactions require server-side distance and quest-state validation."



&#x20; - id: SEC-PP-004

&#x20;   severity: blocker

&#x20;   description: "Solo fallback must exist for onboarding co-op prompts."



&#x20; - id: SEC-PP-005

&#x20;   severity: warning

&#x20;   description: "Custom prompt UI must support touch, keyboard, and gamepad input."

```



\*\*\*



\## 권장 파일 구조



실제로는 아래처럼 Git 저장소 하나에 정리하는 것을 권합니다.



```text

neo-seoul-language-game/

├─ README.md

├─ AGENTS.md

├─ CLAUDE.md

│

├─ wiki/

│  ├─ 00-constitution/

│  │  ├─ product-charter.md

│  │  ├─ non-negotiables.md

│  │  ├─ safety-policy.md

│  │  ├─ pedagogy-language-first.md

│  │  └─ glossary.md

│  │

│  ├─ 10-patterns/

│  │  ├─ onboarding/

│  │  ├─ language/

│  │  ├─ gameplay/

│  │  ├─ ui-ux/

│  │  ├─ safety/

│  │  └─ technical/

│  │

│  ├─ 20-reference/

│  │  ├─ roblox/

│  │  ├─ curriculum/

│  │  ├─ localization/

│  │  └─ research/

│  │

│  └─ 30-decisions/

│     ├─ ADR-001-language-first.md

│     ├─ ADR-002-fictional-gate.md

│     ├─ ADR-003-solo-safe-coop.md

│     └─ ADR-004-no-paid-learning-progress.md

│

├─ specs/

│  ├─ worlds/

│  ├─ curriculum-packs/

│  ├─ localization/

│  ├─ experiments/

│  └─ templates/

│

├─ harness/

│  ├─ product/

│  ├─ curriculum/

│  ├─ ux/

│  ├─ technical/

│  └─ test-scenarios/

│

├─ src/

│  ├─ server/

│  ├─ client/

│  ├─ shared/

│  ├─ ui/

│  └─ world/

│

├─ tests/

│  ├─ unit/

│  ├─ integration/

│  ├─ playtests/

│  └─ screenshots/

│

├─ tools/

│  ├─ validate\_specs.py

│  ├─ build\_localization.py

│  ├─ generate\_world\_manifest.py

│  └─ run\_harness.py

│

└─ output/

&#x20;  ├─ generated\_specs/

&#x20;  ├─ qa\_reports/

&#x20;  └─ review\_packets/

```



\### 중요한 구분



| 영역 | 사람이 주로 수정 | LLM이 수정 가능 | 자동 배포 가능 |

|---|---|---|---|

| `wiki/00-constitution` | 예 | 원칙적으로 금지 | 아니오 |

| `wiki/10-patterns` | 예 | PR 초안만 | 아니오 |

| `wiki/30-decisions` | 예 | 초안 가능 | 아니오 |

| `specs/worlds` | 검토 | 예 | 스테이징만 |

| `specs/localization` | 현지 검수 | 초안 가능 | 스테이징만 |

| `harness` | 예 | 테스트 추가 제안 | 아니오 |

| `src/` | 리뷰 | 예 | 스테이징만 |

| `output/` | 아니오 | 예 | 생성물 |



이 분리가 자동화의 핵심입니다. LLM이 세계관·철학·안전 규칙을 함부로 바꾸지 못하게 하고, 반복 생산물만 빠르게 생성하게 해야 합니다.



\*\*\*



\## 기존 파일을 Wiki로 변환하는 절차



\### 1. 파일을 먼저 “사실/원칙/패턴/명세”로 분류



현재 만든 파일을 그대로 복사하지 마세요. 먼저 아래 표처럼 태그를 붙입니다.



| 파일 내용 | 들어갈 위치 | 변환 방식 |

|---|---|---|

| “수학 언어 친숙화가 목적” | Constitution | 하나의 명확한 제품 원칙으로 압축 |

| “입국심사는 현실 국경이 아님” | Constitution + Safety Pattern | 금지사항과 대체 표현으로 분리 |

| “수학마을 게이트 상세 기획” | Pattern + World Spec | 재사용 로직과 현재 월드 값 분리 |

| “온보딩 UX 팁” | Pattern | 조건·입력·출력·합격 기준으로 변환 |

| “ProximityPrompt Custom UI 코드” | Technical Pattern | 코드와 사용 조건·테스트를 함께 기록 |

| “HoldDuration 게이지” | UI Pattern | 구현 패턴 + 실패 케이스 정리 |

| “다중 조건 서버 검증” | Technical Harness | 테스트 가능한 규칙으로 변환 |

| “LocalizationTable 방법” | Localization Pattern | 키 규약·CSV·UI 규칙으로 변환 |

| “글로벌 히트 특징” | Reference + Decision | 근거와 우리 제품의 결정 분리 |

| “추가 제안” | Idea Backlog | 바로 Wiki 원칙에 섞지 않기 |



\### 2. 중복 문서를 통합하고 충돌을 표시



현재 대화처럼 반복적으로 쌓인 문서에는 같은 내용의 서로 다른 버전이 있을 수 있습니다.



예:



```text

문서 A:

수학마을 입국심사



문서 B:

도시 언어 게이트



문서 C:

탐험 등록소

```



이 셋을 다 살리면 LLM이 랜덤하게 선택합니다. 다음처럼 결정문서로 고정하세요.



```md

\# ADR-002: Fictional Gate Terminology



\## Decision

Use "City Language Gate" as the primary global concept.



\## Why

\- Retains the satisfying gate/clearance fantasy.

\- Avoids real immigration, nationality, visa, and exclusion meanings.

\- Supports the language-first product goal.



\## Allowed secondary labels

\- Explorer Registration Gate

\- Signal Gate

\- Math Village Arrival Gate



\## Prohibited labels

\- immigration checkpoint

\- border control

\- visa approval

\- nationality test

\- entry denial

```



이런 문서가 \*\*ADR(Architecture/Design Decision Record)\*\* 입니다. 중요한 논쟁이 끝날 때마다 하나씩 만들면 LLM도 결정을 다시 뒤집지 않습니다.



\### 3. 모든 Pattern을 “Intent–Mechanic–Guardrail–Test” 형식으로 변환



좋은 Wiki 문서는 설명문이 아니라 실행 가능한 규격입니다.



```md

\# Pattern: City Language Gate



\## Intent

Give a first-session player a 3–5 minute success experience in which

a fictional city responds to their use of everyday and mathematical language.



\## Inputs

\- target term

\- everyday expressions

\- world action

\- NPC helper

\- solo fallback

\- next district



\## Mechanic

1\. Show city problem.

2\. Ask for everyday expression.

3\. Let player act in world.

4\. Show result.

5\. Attach mathematical term after action.

6\. Unlock next area.



\## Guardrails

\- No real immigration imagery.

\- No pass/fail labels.

\- No friend requirement.

\- No term definition before action.

\- No more than one new term in one interaction.



\## Acceptance Tests

\- Player can complete within 5 minutes alone.

\- First interaction happens within 60 seconds.

\- Every term has an everyday-language action.

\- A mathematical term is reusable in at least 3 contexts.

\- Mobile UI fits 360px wide screen.

```



이 형식이면 LLM이 문서를 읽고 구현뿐 아니라 자동 검수까지 연결할 수 있습니다.



\*\*\*



\## `CLAUDE.md` 또는 에이전트 시작 문서



Claude Code가 프로젝트를 열었을 때 가장 먼저 읽을 문서를 루트에 둡니다.



```md

\# CLAUDE.md



\## Role



You are a Roblox production agent for Neo Seoul Language City.



Your job is not to make a math quiz game.

Your job is to build a social adventure in which mathematical language

becomes familiar through meaningful city actions.



\## Read order before any implementation



1\. wiki/00-constitution/product-charter.md

2\. wiki/00-constitution/non-negotiables.md

3\. wiki/00-constitution/pedagogy-language-first.md

4\. wiki/10-patterns/onboarding/city-language-gate.md

5\. relevant specs/worlds/\*.yaml

6\. relevant harness rules



\## Required workflow



1\. Restate the requested world intent.

2\. Identify the applicable patterns and harness rules.

3\. Create or update a world spec before editing Luau.

4\. Produce an implementation plan.

5\. Implement only in development/staging targets.

6\. Run the required harness tests.

7\. Produce a review packet with:

&#x20;  - changed files

&#x20;  - design rationale

&#x20;  - tests passed/failed

&#x20;  - unresolved risks

&#x20;  - localization keys added

8\. Never publish to a production Roblox place without explicit human approval.



\## Hard prohibitions



\- Do not make a multiple-choice quiz loop the core gameplay.

\- Do not gate core progression behind friends, payment, or terminology recall.

\- Do not use real immigration, nationality, visas, or legal citizenship.

\- Do not use learner ranking or public skill labels.

\- Do not implement client-authoritative rewards or progression.

\- Do not remove or weaken harness rules.

```



이 파일 하나가 Claude Code의 기본 행동을 크게 안정시킵니다.



\*\*\*



\## 자동화 워크플로



\### 요청 → 명세 → 코드 → 테스트 → Studio



```text

사람:

"Metro District: 기울기 언어 월드 만들어"



LLM Planner:

\- Wiki 검색

\- Intent 요약

\- 기존 Pattern 선택

\- World Spec 초안 생성



LLM Reviewer:

\- Constitution 위반 검사

\- 교육 언어 흐름 검사

\- 현실 입국심사/시험화 위험 검사



Builder Agent:

\- Luau, UI, Localization Keys, World Manifest 생성



Test Agent:

\- Unit Test

\- Prompt 보안 Test

\- 혼자 NPC 보조 Test

\- 2인 협동 Test

\- 작은 모바일 UI Test

\- 긴 번역 UI Test



Studio MCP:

\- 개발 Place 반영

\- Playtest 실행

\- 화면/로그 수집



Vision/UI Reviewer:

\- Prompt 겹침, 버튼, 텍스트, 길찾기, 월드 가시성 검사



Human:

\- Play / Revise / Reject

```



\### 월드 생성 명령 예시



```text

Create a new world specification for Metro District.



Requirements:

\- Use the Neo Seoul setting.

\- Target 9–14-year-old global players.

\- The learning goal is familiarity with slope language, not assessment.

\- Everyday expressions must precede the term “slope.”

\- The term must be reused in rail, drone, and water-flow contexts.

\- 1–4 players, mobile first.

\- Solo players must receive Line Drone support.

\- Session length: 8 minutes.

\- No quiz screen, no pass/fail language, no paid hints.

\- Use the City Language Gate pattern.

\- Apply all relevant safety, localization, Prompt-security, and mobile UI harness rules.



Output:

1\. specs/worlds/metro-district.yaml

2\. a design rationale

3\. a list of required localization keys

4\. a test plan

Do not write game code yet.

```



이 방식이 중요합니다. 처음부터 코드부터 만들지 말고, 반드시 \*\*Spec을 먼저 생성\*\*하게 해야 합니다.



\*\*\*



\## “LLM Wiki 검색”을 제대로 만드는 법



처음에는 벡터 DB나 복잡한 RAG부터 만들 필요가 없습니다. Claude Code는 Git 저장소 안의 Markdown·YAML을 읽고 검색할 수 있으므로, 아래 규칙만 지켜도 상당히 잘 작동합니다.



\### 초기 버전: 파일 기반 Wiki



```text

Markdown:

원칙, 패턴, 의사결정, 배경 설명



YAML:

구조화된 스펙, 규칙, 테스트 조건



CSV:

번역 키, 용어집, LocalizationTable 데이터



Luau:

실제 구현과 테스트

```



\### 검색 품질을 높이는 작성 규칙



모든 문서 맨 위에 Front Matter를 붙이세요.



```yaml

\---

id: pattern-city-language-gate

type: pattern

status: approved

priority: high

applies\_to:

&#x20; - onboarding

&#x20; - language-learning

&#x20; - neo-seoul

tags:

&#x20; - ftue

&#x20; - city-language

&#x20; - no-quiz

&#x20; - mobile

&#x20; - solo-safe-coop

source\_of\_truth: true

last\_reviewed: 2026-10-01

\---

```



LLM이 검색할 때 “온보딩”, “기울기”, “모바일”, “협동”, “현지화”라는 태그로 관련 문서를 빠르게 찾을 수 있습니다.



\### 나중 버전: 인덱스/검색 에이전트



문서가 수백 개가 되면 다음 파일을 추가합니다.



```text

wiki/

&#x20; index.yaml

&#x20; term-map.yaml

&#x20; pattern-map.yaml

&#x20; rule-map.yaml

```



예시:



```yaml

\# wiki/index.yaml

concepts:

&#x20; slope:

&#x20;   terms:

&#x20;     - wiki/00-constitution/glossary.md#slope

&#x20;     - wiki/10-patterns/language/everyday-to-math-term.md

&#x20;   worlds:

&#x20;     - specs/worlds/metro-district.yaml

&#x20;   harness:

&#x20;     - harness/curriculum/term-context-validation.yaml

&#x20;     - harness/product/language-first-rules.yaml



&#x20; onboarding:

&#x20;   patterns:

&#x20;     - wiki/10-patterns/onboarding/city-language-gate.md

&#x20;     - wiki/10-patterns/onboarding/delayed-hints.md

&#x20;   tests:

&#x20;     - harness/test-scenarios/gate-solo.yaml

&#x20;     - harness/test-scenarios/gate-two-player.yaml

```



에이전트는 이 인덱스를 먼저 읽고, 필요한 문서만 깊게 읽게 하면 토큰과 혼란을 줄일 수 있습니다.



\*\*\*



\## Harness를 코드로 실행하기



LLM에게 “문서를 읽어라”라고만 하면 준수 여부가 불안정합니다. 가능하면 규칙 일부는 코드 검사로 바꿔야 합니다.



\### 예: 금지 표현 검사



```python

\# tools/validate\_copy.py

from pathlib import Path



BANNED = {

&#x20;   "ko": \["오답", "불합격", "입국 거부", "수학을 못해"],

&#x20;   "en": \["wrong answer", "entry denied", "you failed math"],

}



for path in Path("specs").rglob("\*.\*"):

&#x20;   if path.suffix not in {".yaml", ".yml", ".md", ".csv"}:

&#x20;       continue



&#x20;   text = path.read\_text(encoding="utf-8")

&#x20;   for lang, phrases in BANNED.items():

&#x20;       for phrase in phrases:

&#x20;           if phrase.lower() in text.lower():

&#x20;               raise SystemExit(f"Banned phrase: {phrase} in {path}")

```



\### 예: 용어 재사용 검사



```yaml

\# harness/curriculum/term-context-validation.yaml

required:

&#x20; each\_term:

&#x20;   min\_distinct\_contexts: 3

&#x20;   requires:

&#x20;     - everyday\_expression

&#x20;     - world\_action

&#x20;     - post\_action\_label

&#x20;     - reuse\_context

```



이를 읽는 검증 스크립트는 `specs/worlds/\*.yaml`에서 `term\_id`가 최소 세 개의 다른 `context\_id`에 나타나는지 검사합니다.



\### 예: 솔로 대체 검사



```yaml

\# harness/ux/coop-rules.yaml

rules:

&#x20; - id: COOP-001

&#x20;   severity: blocker

&#x20;   condition: "onboarding\_coop\_mission"

&#x20;   requires:

&#x20;     - npc\_fallback

&#x20;     - max\_matchmaking\_wait\_seconds\_lte: 10

&#x20;     - solo\_completion\_path: true

```



이렇게 하면 AI가 “친구 두 명이 동시에 버튼을 눌러야만 통과” 같은 설계를 만들었을 때 자동으로 빌드를 막을 수 있습니다.



\*\*\*



\## 콘텐츠 생성 파이프라인



수백 개 월드를 만들고 싶다면 아래 단위로 공장을 설계하세요.



```text

Curriculum Pack

\+ World Theme

\+ Language Term Pack

\+ Gameplay Pattern

\+ UI Pattern

\+ Localization Pack

\+ Harness Pack

= Playable World Candidate

```



\### 예시 조합



```text

Curriculum:

\- position-and-coordinate language



World:

\- Neo Seoul Metro District



Gameplay:

\- cooperative route repair



Language:

\- right/left/up/down → coordinate



UI:

\- expression wheel + world prompt



Harness:

\- no quiz loop

\- solo fallback

\- mobile-safe UI

\- term reuse 3 contexts

\- server-authoritative rewards

```



새 월드는 “빈 종이에서 생성”하지 말고, 이 조합을 명시적으로 선택하게 하세요.



```yaml

world\_recipe:

&#x20; curriculum\_pack: coordinate\_language\_v1

&#x20; world\_theme: neo\_seoul\_metro

&#x20; gameplay\_pattern: cooperative\_route\_repair

&#x20; language\_pattern: everyday\_to\_term

&#x20; ui\_pattern: expression\_wheel

&#x20; coop\_pattern: solo\_safe\_coop

&#x20; harness\_pack:

&#x20;   - language\_first

&#x20;   - mobile\_ui

&#x20;   - prompt\_security

&#x20;   - localization

```



이 `world\_recipe`가 자동 생산의 진짜 단위입니다.



\*\*\*



\## 30일 구축 순서



\### 1주차: 문서 정리와 헌법 고정



\- 기존 파일을 모두 한 폴더에 모읍니다.

\- 문서마다 `원칙 / 패턴 / 현재 기획 / 참고 / 아이디어` 태그를 붙입니다.

\- `product-charter.md`와 `non-negotiables.md`를 확정합니다.

\- “입국심사” 용어를 “도시 언어 게이트”로 공식 결정합니다.

\- 최소 5개 ADR을 만듭니다.



\### 2주차: Pattern과 Spec 분리



\- 수학마을 게이트를 Pattern으로 변환합니다.

\- Neo Seoul Central을 첫 World Spec으로 만듭니다.

\- Metro District를 두 번째 World Spec으로 만듭니다.

\- 용어·일상어·피드백·협동 핑을 키 기반 LocalizationTable 구조로 정리합니다.

\- `CLAUDE.md`와 `AGENTS.md`를 작성합니다.



\### 3주차: 최소 Harness 구현



\- 금지 문구 검사

\- 용어→행동→이름표 순서 검사

\- 솔로 NPC 대체 검사

\- 프롬프트 서버 검증 검사

\- 중복 보상 검사

\- 작은 모바일 UI 스크린샷 검사

\- 긴 번역문 UI 검사



\### 4주차: 첫 자동 생성 실험



\- “좌표 언어 게이트” 한 개만 자동 생성하게 합니다.

\- LLM이 Spec → Localization Keys → Luau 초안 → 테스트 계획 순으로 만들게 합니다.

\- Studio MCP로 개발 Place에 반영합니다.

\- 실제 플레이 5\~10명 관찰합니다.

\- Wiki, Pattern, Harness에서 빠진 규칙을 보완합니다.



처음부터 150개 월드를 자동 생산하지 마세요. \*\*한 개의 도시 언어 게이트가 Wiki 규칙을 지키며, 재미·안전·모바일·현지화 조건을 통과하는지\*\*가 먼저 증명되어야 합니다.



\*\*\*



\## 최종 원칙



이 자동화 시스템은 “AI에게 Roblox 게임을 만들어 달라”는 구조가 아닙니다.



```text

나쁜 자동화:

자연어 요청

→ LLM이 즉흥 기획

→ Luau 생성

→ 배포

→ 품질 불명



좋은 자동화:

헌법

→ 패턴

→ 구조화된 월드 Spec

→ 코드 생성

→ Harness 검증

→ Studio 플레이테스트

→ 사람 승인

→ 제한 출시

→ 플레이 데이터

→ Wiki와 Pattern 개선

```



결론적으로, 지금까지 만든 파일은 이미 매우 좋은 원료입니다. 이를 \*\*LLM Wiki + 구조화된 Specs + 실행 가능한 Harness\*\*로 바꾸면, Claude Code와 Roblox Studio MCP가 임의로 게임을 만드는 도구가 아니라, 당신의 제품 철학을 반복 생산하는 \*\*Neo Seoul 게임 제작 공장\*\*으로 작동할 수 있습니다.

