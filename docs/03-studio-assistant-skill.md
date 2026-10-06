# Studio 어시스턴트 스킬 — rb-city-language-gate

Roblox Studio 어시스턴트(Studio AI)가 이 프로젝트의 설계 규칙을 따르게 하는 **사용자 스킬** 원고다.
설계 정본(`intent.md`·`decisions.md`·`world/src/shared/Layout.luau`·명세)에서 Claude Code 가 뽑아 만든다. 설계가 바뀌면 이 파일을 다시 만든다.

- 등록: Studio 어시스턴트(Agent)에 "아래 이름·설명·본문으로 스킬을 만들어 줘(create_skill)" 라고 쓰고 아래 세 덩어리를 붙여 넣는다. 등록하면 설정 → 스킬 → 개인에 보인다.
- 갱신: 이 파일이 바뀌면 "rb-city-language-gate 스킬 본문을 아래로 바꿔 줘(edit_skill)" 로 본문만 다시 붙여 넣는다.
- 근거: Studio 의 `rbx-create-skill` 지침(이름은 `rbx-` 로 시작 불가, 64자 이내, 본문은 머리말 없는 마크다운, 500줄 이내).

## 이름

```
rb-city-language-gate
```

## 설명

```
도시 언어 게이트(rb) 스테이징 Place 의 설계 규칙을 따르게 한다. rb-staging Place 에서 월드·장식·조명·UI·스크립트를 만들거나 고치거나 Play 로 시험할 때, 또는 CityLanguageGateWorld·SignalPanel·LightBridge·GateDeck·ZonePortal 같은 이름이 나올 때 사용한다.
```

## 본문

```markdown
# 도시 언어 게이트 (rb) — Studio 작업 규칙

이 Place 는 9~14세가 수학 표현(좌표·기울기)을 일상어처럼 쓰게 하는 Roblox 월드 '도시 언어 게이트'의 스테이징 Place(rb-staging.rbxlx, 미게시)다. 설계 정본은 Git 저장소에 있고 Claude Code 가 관리한다. 아래는 그 정본에서 뽑은 Studio 작업 규칙이다.

## 1. 고쳐도 되는 것과 안 되는 것 (DEC-8)
- 고치지 않는다 — 저장소가 정본이고 Rojo 가 덮어쓴다: ServerScriptService.Gate, ReplicatedStorage.Shared(번역표 Localization 포함), StarterPlayer.StarterPlayerScripts.Gate 아래 모든 것. 고칠 점이 보이면 고치지 말고 경로·이유·제안 코드를 보고한다.
- Workspace 에 CityLanguageGateWorld 를 만들지 않는다. 게임이 시작될 때 서버가 이 폴더와 기능 오브젝트를 만든다. 같은 이름이 미리 있으면 서버가 아무것도 만들지 않아 게임이 깨진다. 편집 모드에서 이 폴더가 안 보이는 것이 정상이다.
- Studio 에서 해도 되는 것: 지형, 도시 외관·배경 장식, 조명·하늘. 새 장식은 Workspace.CityDecor 같은 별도 폴더에 둔다.
- 게시, 팀 Place 만들기, 배지·상품 만들기, 다른 Place 열기는 하지 않는다(사람이 정한다, DEC-2).

## 2. 서버가 만드는 기능 오브젝트 (코드가 이름으로 찾는다)
CityLanguageGateWorld 안: SignalWall(칸 cell_x_y, x·y −2..2, 출발 칸 표시 StartPad), SignalPanel(프롬프트 ActivatePrompt), LightBridge(끝 막대 BridgeEnd), BridgeStart, GateDeck, GateThreshold, CityLanguageGate(불 GateLamp1..3), gate_prism_left, gate_prism_right, CityLights(CityTower 6개), Lumi, ZonePortal(프롬프트 EnterPrompt).
Play 중에 이 이름들을 바꾸거나 지우거나 옮기지 않는다.

## 3. 배치 — 장식이 길과 시선을 막지 않게
- 출발점 (0, 0, 0) 에서 −Z 쪽으로 나아간다.
- 신호판 중심 (−18, 12, −22), 신호 패널 (−10, 3, −12), 빛 다리 출발 (0, 0.5, −16) 가로 거리 12, 게이트 단 앞면 z = −28·윗면 y = 13, 게이트 (0, 22, −31), 포털 (0, 18, −50), 협동 프리즘 (±6, 2, −20).
- 출발점에서 게이트 단까지의 길(x −4..4)과 게이트 단 위(x −8..8, z −28..−60)는 비워 둔다.
- 출발 지점과 신호 패널 앞에서 게이트와 신호판이 보여야 한다 — 그 사이에 시선을 막는 장식을 두지 않는다.
- 게이트 단(높이 13)은 빛 다리로만 오른다 — 단 옆·뒤에 계단·발판·경사를 두지 않는다.

## 4. 색과 빛 — 게임 신호와 헷갈리지 않게 (INV-9)
- 게임 신호: 노랑 발광 깜박임 = 지금 할 곳, 청록 발광 고정 = 돌아온 신호, 크림 = 출발 표시, 남색 = 꺼진 구조.
- 장식에는 노랑·청록 Neon 과 깜박임을 쓰지 않는다. 빨강으로 실패를 나타내지 않는다.
- 뜻을 색만으로 전하지 않는다 — 모양·밝기·움직임을 함께 쓴다.

## 5. 하지 않는 것
- 월드와 코드에 화면 문구를 직접 넣지 않는다: SurfaceGui·BillboardGui·TextLabel·글자 Decal 금지. 화면 문구는 모두 번역표 키로만 넣는다(INV-3).
- 판정·보상은 서버만 정한다(INV-4). 무작위·유료 보상, 카운트다운·시간 압박을 만들지 않는다(INV-12·INV-14).
- 자유 입력창(TextBox), 외부 링크·주소를 넣지 않는다(INV-16).

## 6. Claude Code 와 함께 쓰기
- Claude Code 가 같은 Studio 를 MCP 로 쓴다. Play 시험은 한 번에 한쪽만 한다 — Play 를 시작하거나 조작하기 전에 사람에게 Claude Code 가 지금 시험 중인지 묻는다.
- Studio 를 바꾸기 전에 열린 Place 가 rb-staging.rbxlx 인지 확인한다.
- 일을 마치면 바꾼 Instance 경로, 바꾼 이유, Play 확인 결과를 보고한다(사람이 Claude Code 에 옮겨 기록한다).
```
