`ProximityPromptService` 전역 이벤트는 게임 안의 모든 `ProximityPrompt`를 한곳에서 감시·처리하는 방식입니다. 각 패널·NPC·게이트마다 스크립트를 따로 붙이는 대신, \*\*클라이언트는 UI·연출을 담당하고 서버는 상호작용 검증·진도·보상을 담당하는 두 개의 전역 라우터\*\*를 두는 것이 가장 안정적입니다.



Roblox는 `ProximityPromptService`에서 `PromptShown`, `PromptHidden`, `PromptButtonHoldBegan`, `PromptButtonHoldEnded`, `PromptTriggered` 등 전체 Prompt의 이벤트를 제공하며, 특히 표시/숨김은 LocalScript에서 UI 제어에, 트리거는 서버에서 게임 상태 검증에 활용할 수 있습니다. \[create.roblox](https://create.roblox.com/docs/reference/engine/classes/ProximityPromptService/PromptButtonHoldBegan)



\## 이벤트 역할



| 이벤트 | 실행 위치 | 언제 발생 | 주 용도 |

|---|---|---|---|

| `PromptShown` | 클라이언트 | Prompt가 화면에 표시됨 | 커스텀 UI 생성, Highlight 켜기 |

| `PromptHidden` | 클라이언트 | Prompt가 사라짐 | UI·Tween·입력 연결 정리 |

| `PromptButtonHoldBegan` | 클라이언트/서버 | `HoldDuration > 0` Prompt의 홀드 시작 | 홀드 게이지·사운드 시작 |

| `PromptButtonHoldEnded` | 클라이언트/서버 | 홀드 취소 또는 종료 | 게이지 취소·상태 정리 |

| `PromptTriggered` | 서버 중심 | 즉시 입력 또는 홀드 완료 | 거리·퀘스트·보상 검증, 상태 전환 |

| `PromptTriggerEnded` | 클라이언트/서버 | 상호작용 종료 | 채널링·지속 상호작용 정리 |

| `IndicatorShown` / `IndicatorHidden` | 클라이언트 | 화면 밖/거리 상태의 인디케이터 변화 | 월드 방향 표식·미니맵 보조 |



`PromptButtonHoldBegan`은 `HoldDuration`이 0이 아닌 Prompt에서 플레이어가 키/버튼을 누르기 시작했을 때 발생합니다. \[create.roblox](https://create.roblox.com/docs/reference/engine/classes/ProximityPromptService/PromptButtonHoldBegan)



\## 권장 아키텍처



```text

Workspace의 여러 ProximityPrompt

&#x20;          │

&#x20;          ├─ ClientPromptController (LocalScript)

&#x20;          │   ├─ PromptShown / Hidden

&#x20;          │   ├─ Custom UI 생성·제거

&#x20;          │   ├─ 홀드 게이지 Tween

&#x20;          │   ├─ Highlight·사운드·햅틱

&#x20;          │   └─ 모바일 TouchButton 입력

&#x20;          │

&#x20;          └─ ServerPromptRouter (Script)

&#x20;              ├─ PromptTriggered

&#x20;              ├─ InteractionId 기준 Handler 분기

&#x20;              ├─ 상태·거리·쿨다운·팀 조건 검증

&#x20;              ├─ 퀘스트 진행 및 보상

&#x20;              └─ FeedbackEvent로 클라이언트에 결과 전달

```



이렇게 하면 새 Prompt를 추가할 때 Studio에서 Attribute만 설정하고, 코드 라우터에 Handler를 하나 추가하는 방식으로 확장할 수 있습니다.



\## Prompt Attribute 설계



모든 Prompt에 아래처럼 Attribute를 붙이세요.



```lua

prompt:SetAttribute("InteractionId", "signal\_1\_activate")

prompt:SetAttribute("QuestId", "math\_village\_gate")

prompt:SetAttribute("RequiredState", "MOVE\_TO\_SIGNAL\_1")

prompt:SetAttribute("NextState", "SIGNAL\_1\_DONE")

prompt:SetAttribute("PromptTheme", "signal")

prompt:SetAttribute("Priority", 10)

```



수학마을 예시입니다.



| `InteractionId` | 대상 | 필요 상태 | 다음 상태 |

|---|---|---|---|

| `signal\_1\_activate` | 첫 신호 패널 | `MOVE\_TO\_SIGNAL\_1` | `SIGNAL\_1\_DONE` |

| `drone\_console\_open` | 드론 콘솔 | `SIGNAL\_1\_DONE` | `COORDINATE\_SIGNAL\_2` |

| `prism\_left\_ready` | 좌측 프리즘 | `COOP\_SIGNAL\_3` | 팀 준비 상태 |

| `prism\_right\_ready` | 우측 프리즘 | `COOP\_SIGNAL\_3` | 팀 준비 상태 |

| `lumi\_help` | 루미 NPC | 모든 온보딩 상태 | 상태 유지 |

| `metro\_portal\_enter` | Metro 포털 | `GATE\_OPENED` | `METRO\_ENTERED` |



프롬프트의 이름이나 Parent 경로만 기준으로 분기하면 월드 복제·다국어·재사용 템플릿에서 관리가 어려워집니다. `InteractionId`를 안정적인 식별자로 쓰세요.



\## 클라이언트 전역 컨트롤러



아래는 `StarterPlayerScripts`에 두는 기본 구조입니다. 커스텀 UI뿐 아니라 Default Prompt의 월드 강조에도 쓸 수 있습니다.



```lua

\-- StarterPlayerScripts/ClientPromptController.client.lua



local ProximityPromptService = game:GetService("ProximityPromptService")

local TweenService = game:GetService("TweenService")



local active = {}



local function getTarget(prompt)

&#x20;   local parent = prompt.Parent



&#x20;   if parent:IsA("Attachment") then

&#x20;       return parent.Parent

&#x20;   end



&#x20;   if parent:IsA("BasePart") then

&#x20;       return parent

&#x20;   end



&#x20;   if parent:IsA("Model") then

&#x20;       return parent.PrimaryPart

&#x20;   end



&#x20;   return nil

end



local function createHighlight(target)

&#x20;   if not target then

&#x20;       return nil

&#x20;   end



&#x20;   local highlight = Instance.new("Highlight")

&#x20;   highlight.Name = "LocalPromptHighlight"

&#x20;   highlight.Adornee = target

&#x20;   highlight.FillTransparency = 0.82

&#x20;   highlight.OutlineTransparency = 0.2

&#x20;   highlight.FillColor = Color3.fromRGB(38, 218, 181)

&#x20;   highlight.OutlineColor = Color3.fromRGB(255, 214, 89)

&#x20;   highlight.DepthMode = Enum.HighlightDepthMode.Occluded

&#x20;   highlight.Parent = target



&#x20;   return highlight

end



local function destroyActive(prompt)

&#x20;   local state = active\[prompt]

&#x20;   if not state then

&#x20;       return

&#x20;   end



&#x20;   if state.holdTween then

&#x20;       state.holdTween:Cancel()

&#x20;   end



&#x20;   if state.highlight then

&#x20;       state.highlight:Destroy()

&#x20;   end



&#x20;   if state.gui then

&#x20;       state.gui:Destroy()

&#x20;   end



&#x20;   active\[prompt] = nil

end



ProximityPromptService.PromptShown:Connect(function(prompt, inputType)

&#x20;   local target = getTarget(prompt)



&#x20;   active\[prompt] = {

&#x20;       target = target,

&#x20;       inputType = inputType,

&#x20;       highlight = createHighlight(target),

&#x20;   }



&#x20;   if prompt.Style == Enum.ProximityPromptStyle.Custom then

&#x20;       -- createCustomGui(prompt, inputType)를 여기서 호출

&#x20;       -- active\[prompt].gui = gui

&#x20;   end

end)



ProximityPromptService.PromptHidden:Connect(function(prompt)

&#x20;   destroyActive(prompt)

end)



ProximityPromptService.PromptButtonHoldBegan:Connect(function(prompt)

&#x20;   local state = active\[prompt]

&#x20;   if not state or prompt.HoldDuration <= 0 then

&#x20;       return

&#x20;   end



&#x20;   -- Custom UI의 HoldBar.Fill을 찾아 채우는 구현

&#x20;   if state.gui then

&#x20;       local fill = state.gui.Card.HoldBar.Fill

&#x20;       fill.Size = UDim2.fromScale(0, 1)



&#x20;       state.holdTween = TweenService:Create(

&#x20;           fill,

&#x20;           TweenInfo.new(prompt.HoldDuration, Enum.EasingStyle.Linear),

&#x20;           { Size = UDim2.fromScale(1, 1) }

&#x20;       )



&#x20;       state.holdTween:Play()

&#x20;   end

end)



ProximityPromptService.PromptButtonHoldEnded:Connect(function(prompt)

&#x20;   local state = active\[prompt]

&#x20;   if not state then

&#x20;       return

&#x20;   end



&#x20;   if state.holdTween then

&#x20;       state.holdTween:Cancel()

&#x20;       state.holdTween = nil

&#x20;   end



&#x20;   if state.gui then

&#x20;       local fill = state.gui.Card.HoldBar.Fill



&#x20;       TweenService:Create(

&#x20;           fill,

&#x20;           TweenInfo.new(0.12, Enum.EasingStyle.Quad, Enum.EasingDirection.Out),

&#x20;           { Size = UDim2.fromScale(0, 1) }

&#x20;       ):Play()

&#x20;   end

end)



ProximityPromptService.PromptTriggered:Connect(function(prompt)

&#x20;   local state = active\[prompt]

&#x20;   if not state then

&#x20;       return

&#x20;   end



&#x20;   if state.highlight then

&#x20;       state.highlight.OutlineColor = Color3.fromRGB(38, 218, 181)

&#x20;   end



&#x20;   -- 이곳은 로컬 성공 사운드/진동/짧은 연출만 처리.

&#x20;   -- 보상·퀘스트 완료 판단은 서버가 처리.

end)

```



`PromptShown`과 `PromptHidden`은 Prompt의 표시 상태에 맞춰 UI를 생성·정리하는 데 사용합니다. 표시/숨김 이벤트는 LocalScript에서 UI를 제어하는 용도에 적합합니다. \[create.roblox](https://create.roblox.com/docs/reference/engine/classes/ProximityPromptService/PromptButtonHoldBegan)



\## 서버 전역 라우터



`ServerScriptService`에 하나의 Script를 두고 모든 `PromptTriggered`를 라우팅합니다.



```lua

\-- ServerScriptService/ServerPromptRouter.server.lua



local ProximityPromptService = game:GetService("ProximityPromptService")

local ReplicatedStorage = game:GetService("ReplicatedStorage")



local FeedbackEvent = ReplicatedStorage.Remotes.FeedbackEvent



local PlayerStateService = require(script.Parent.Services.PlayerStateService)

local GateService = require(script.Parent.Services.GateService)

local RewardService = require(script.Parent.Services.RewardService)



local lastTriggerAt = {}



local function isRateLimited(player, interactionId)

&#x20;   local key = string.format("%d:%s", player.UserId, interactionId)

&#x20;   local now = os.clock()

&#x20;   local previous = lastTriggerAt\[key]



&#x20;   if previous and now - previous < 0.35 then

&#x20;       return true

&#x20;   end



&#x20;   lastTriggerAt\[key] = now

&#x20;   return false

end



local function validPromptState(player, prompt)

&#x20;   local requiredState = prompt:GetAttribute("RequiredState")



&#x20;   if not requiredState or requiredState == "" then

&#x20;       return true

&#x20;   end



&#x20;   return PlayerStateService:getState(player) == requiredState

end



local function validDistance(player, prompt)

&#x20;   return GateService:isPlayerNearPrompt(player, prompt, 12)

end



local handlers = {}



handlers.signal\_1\_activate = function(player, prompt)

&#x20;   if not GateService:activateSignal(player, "signal\_1") then

&#x20;       return

&#x20;   end



&#x20;   PlayerStateService:setState(player, "SIGNAL\_1\_DONE")



&#x20;   FeedbackEvent:FireClient(player, {

&#x20;       eventId = "signal\_1\_success",

&#x20;       kind = "success",

&#x20;       titleKey = "feedback.signal\_1.title",

&#x20;       bodyKey = "feedback.signal\_1.body",

&#x20;       progress = { current = 1, total = 3 },

&#x20;       visual = {

&#x20;           targetId = "GateRing\_01",

&#x20;           effect = "activate",

&#x20;           color = "teal",

&#x20;       },

&#x20;       duration = 2.5,

&#x20;   })

end



handlers.prism\_left\_ready = function(player, prompt)

&#x20;   local result = GateService:markCoopReady(player, "left")



&#x20;   if result == "waiting" then

&#x20;       FeedbackEvent:FireClient(player, {

&#x20;           eventId = "coop\_waiting",

&#x20;           kind = "team",

&#x20;           titleKey = "feedback.coop.waiting.title",

&#x20;           bodyKey = "feedback.coop.waiting.body",

&#x20;           duration = 2.5,

&#x20;       })

&#x20;   elseif result == "success" then

&#x20;       GateService:openGateForTeam(player)

&#x20;       RewardService:grantGateCompletionOnce(player)

&#x20;   end

end



handlers.lumi\_help = function(player)

&#x20;   local state = PlayerStateService:getState(player)

&#x20;   local hint = GateService:getContextualHint(player, state)



&#x20;   FeedbackEvent:FireClient(player, hint)

end



ProximityPromptService.PromptTriggered:Connect(function(prompt, player)

&#x20;   local interactionId = prompt:GetAttribute("InteractionId")



&#x20;   if not interactionId then

&#x20;       return

&#x20;   end



&#x20;   local handler = handlers\[interactionId]

&#x20;   if not handler then

&#x20;       warn("No handler for InteractionId:", interactionId)

&#x20;       return

&#x20;   end



&#x20;   if isRateLimited(player, interactionId) then

&#x20;       return

&#x20;   end



&#x20;   if not validPromptState(player, prompt) then

&#x20;       return

&#x20;   end



&#x20;   if not validDistance(player, prompt) then

&#x20;       return

&#x20;   end



&#x20;   handler(player, prompt)

end)

```



`PromptTriggered`는 모든 Prompt의 실제 상호작용 완료 시 발생합니다. 홀드 Prompt라면 설정된 `HoldDuration`이 충족된 뒤 발생합니다. 서버 라우터에서는 이 이벤트를 시작점으로 쓰되, 반드시 거리·퀘스트 상태·중복·팀 조건을 검증해야 합니다. \[create.roblox](https://create.roblox.com/docs/reference/engine/classes/ProximityPromptService/PromptButtonHoldBegan)



\## Custom Prompt와 입력 처리



전역 이벤트는 UI 이벤트를 모으는 역할입니다. `Style = Custom`인 경우에는 UI 버튼의 입력을 Prompt에 다시 전달해야 합니다.



```lua

local function bindCustomButton(prompt, button)

&#x20;   local holding = false



&#x20;   button.InputBegan:Connect(function(input)

&#x20;       local isPress =

&#x20;           input.UserInputType == Enum.UserInputType.Touch

&#x20;           or input.UserInputType == Enum.UserInputType.MouseButton1



&#x20;       if isPress and not holding then

&#x20;           holding = true

&#x20;           prompt:InputHoldBegin()

&#x20;       end

&#x20;   end)



&#x20;   button.InputEnded:Connect(function(input)

&#x20;       local isRelease =

&#x20;           input.UserInputType == Enum.UserInputType.Touch

&#x20;           or input.UserInputType == Enum.UserInputType.MouseButton1



&#x20;       if isRelease and holding then

&#x20;           holding = false

&#x20;           prompt:InputHoldEnd()

&#x20;       end

&#x20;   end)

end

```



이후 전역 `PromptButtonHoldBegan`과 `PromptButtonHoldEnded` 이벤트가 발생하며, 같은 컨트롤러가 홀드 게이지를 애니메이션할 수 있습니다.



\## 실전 이벤트 사용 예



\### 1. `PromptShown`: 다음 행동 강조



```lua

ProximityPromptService.PromptShown:Connect(function(prompt, inputType)

&#x20;   if prompt:GetAttribute("Priority") == 10 then

&#x20;       showWorldArrow(prompt)

&#x20;       enableHighlight(prompt)

&#x20;   end

end)

```



수학마을 첫 신호 패널에서는 Prompt가 보일 때 바닥 빛 경로·드론·Highlight를 켜서 플레이어가 “무엇을 만지는지” 알게 합니다.



\### 2. `PromptButtonHoldBegan`: 협동 준비 연출



```lua

ProximityPromptService.PromptButtonHoldBegan:Connect(function(prompt)

&#x20;   if prompt:GetAttribute("InteractionId") == "prism\_left\_ready" then

&#x20;       setLocalTeamStatus("charging")

&#x20;       startHoldGauge(prompt.HoldDuration)

&#x20;       startSwitchGlow(prompt)

&#x20;   end

end)

```



\### 3. `PromptButtonHoldEnded`: 취소 피드백



```lua

ProximityPromptService.PromptButtonHoldEnded:Connect(function(prompt)

&#x20;   if prompt:GetAttribute("InteractionId") == "prism\_left\_ready" then

&#x20;       cancelHoldGauge()

&#x20;       setLocalTeamStatus("not\_ready")

&#x20;       dimSwitchGlow(prompt)

&#x20;   end

end)

```



\### 4. `PromptTriggered`: 서버 결과와 분리



```lua

\-- 클라이언트

ProximityPromptService.PromptTriggered:Connect(function(prompt)

&#x20;   playLocalClickFeedback(prompt)

end)



\-- 서버

ProximityPromptService.PromptTriggered:Connect(function(prompt, player)

&#x20;   validateAndAdvanceQuest(prompt, player)

end)

```



클라이언트에서는 즉각 반응성—클릭음, 가벼운 햅틱, 게이지 완료—을 보여 주고, 서버에서는 권한이 필요한 상태 변경을 처리합니다.



\## 중요한 주의점



\### 클라이언트에서 만든 Prompt는 서버가 못 본다



클라이언트 LocalScript에서만 Prompt를 Clone하면 서버의 `PromptTriggered` 라우터는 그 인스턴스를 볼 수 없습니다. 실제 상호작용·보상·진도에 쓰는 Prompt는 서버에서 생성하거나, Studio에 미리 두어 서버에 복제되게 하세요. 런타임 생성이 필요하면 서버 Script에서 생성해야 합니다. \[devforum.roblox](https://devforum.roblox.com/t/issues-with-proximitypromptservice-prompttriggered-event-not-firing/3127664)



\### `PromptShown`은 UI, `PromptTriggered`는 게임 로직



권장 분리입니다.



```text

클라이언트:

PromptShown / Hidden

PromptButtonHoldBegan / Ended

→ UI, Highlight, Tween, 사운드, 햅틱



서버:

PromptTriggered

→ 거리, 상태, 팀, 쿨다운, 보상, 저장, 텔레메트리

```



\### 전역 이벤트라도 필터링이 필요



전역 라우터는 모든 Prompt를 받습니다. 다른 시스템의 Prompt까지 처리하지 않도록 Attribute나 `CollectionService` 태그로 범위를 제한하세요.



```lua

if not prompt:GetAttribute("InteractionId") then

&#x20;   return

end

```



또는:



```lua

local CollectionService = game:GetService("CollectionService")



if not CollectionService:HasTag(prompt, "MathVillagePrompt") then

&#x20;   return

end

```



\### `PromptHidden`에서 리소스 정리



Custom UI를 만들었다면 Prompt가 사라질 때 다음을 반드시 정리하세요.



```text

\- BillboardGui / ScreenGui clone

\- TweenService Tween

\- InputBegan / InputEnded 연결

\- Highlight

\- 사운드 루프

\- 로컬 상태 테이블

```



그렇지 않으면 UI가 남거나, 다음 Prompt에서 입력이 중복되고, 성능이 떨어집니다.



\## 테스트 체크리스트



```text

\[전역 라우팅]

\- 새 Prompt 추가 후 Attribute만 설정해도 Handler가 동작한다.

\- 다른 월드/다른 시스템 Prompt는 무시된다.

\- Handler가 없는 InteractionId는 경고만 남기고 보상하지 않는다.



\[클라이언트]

\- PromptShown에서 UI/Highlight가 생긴다.

\- PromptHidden에서 UI/Tween/연결이 모두 사라진다.

\- Hold 시작/취소/완료가 시각적으로 일치한다.

\- 터치, 키보드, 게임패드에서 표시와 입력이 맞다.



\[서버]

\- 현재 퀘스트 상태가 아니면 처리되지 않는다.

\- 거리 밖에서 Trigger해도 처리되지 않는다.

\- 같은 Prompt 연타로 보상이 중복되지 않는다.

\- 협동 Prompt는 팀원 이탈·재접속을 처리한다.

\- 서버에서 생성된 Prompt만 운영 로직에 사용한다.

```



\## 결론



`ProximityPromptService` 전역 이벤트의 핵심은 다음 한 줄입니다.



> \*\*Prompt는 월드 곳곳에 두고, 행동 규칙은 중앙에서 관리한다.\*\*



```text

PromptShown / Hidden

→ 클라이언트 UI와 월드 강조



HoldBegan / HoldEnded

→ 홀드 게이지와 상호작용 연출



PromptTriggered

→ 서버 상태 검증·퀘스트 전환·보상



Attribute / Tag

→ 어떤 Prompt가 어떤 Handler를 써야 하는지 식별

```



이 구조를 쓰면 수학마을의 신호 패널, 드론 콘솔, 협동 스위치, NPC, 자격증 게시판, 포털을 같은 프레임워크로 운영하면서도, 각 오브젝트의 수학·협동·피드백 로직은 안전하게 분리할 수 있습니다.

