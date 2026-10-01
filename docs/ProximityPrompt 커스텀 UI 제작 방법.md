`ProximityPrompt` 커스텀 UI는 `Style = Custom`으로 기본 Roblox 프롬프트를 끄고, LocalScript가 프롬프트 표시·입력·홀드 게이지·숨김을 직접 담당하는 방식입니다. 실제 보상·퀘스트 완료·시민권 발급은 클라이언트 UI가 아니라 서버의 `PromptTriggered` 검증으로만 처리해야 합니다. \[create.roblox](https://create.roblox.com/docs/reference/engine/classes/ProximityPrompt/Style)



\## 구현 구조



```text

Workspace 오브젝트

&#x20; └─ Attachment

&#x20;     └─ ProximityPrompt (Style = Custom)

&#x20;         ↓

LocalScript

&#x20; ├─ PromptShown → BillboardGui 생성

&#x20; ├─ InputHoldBegin → 홀드 시작

&#x20; ├─ PromptButtonHoldBegan → 게이지 애니메이션

&#x20; ├─ PromptButtonHoldEnded → 게이지 취소/리셋

&#x20; └─ PromptHidden → UI·이벤트 제거

&#x20;         ↓

Server Script

&#x20; └─ PromptTriggered → 거리/퀘스트/중복 검증 → 월드 상태·보상 처리

```



대규모 게임에서는 Prompt마다 LocalScript를 두지 말고 `ProximityPromptService`의 전역 이벤트를 쓰는 것이 좋습니다. `PromptShown`, `PromptHidden`, 홀드 시작/종료 이벤트를 한 컨트롤러에서 처리할 수 있습니다. \[robloxapi.github](https://robloxapi.github.io/ref/class/ProximityPrompt)



\## 1. Prompt 설정



예: 수학마을의 협동 프리즘 스위치.



```lua

\-- ServerScriptService/SetupPrompt.server.lua

local switch = workspace.MathVillage.PrismSwitchLeft

local attachment = switch:WaitForChild("Attachment")



local prompt = Instance.new("ProximityPrompt")

prompt.Name = "PrismSwitchPrompt"



prompt.ActionText = "신호 준비"

prompt.ObjectText = "프리즘 스위치"



prompt.Style = Enum.ProximityPromptStyle.Custom

prompt.HoldDuration = 0.6



prompt.MaxActivationDistance = 8

prompt.MaxIndicatorDistance = 16

prompt.RequiresLineOfSight = false

prompt.ClickablePrompt = true



prompt.KeyboardKeyCode = Enum.KeyCode.E

prompt.GamepadKeyCode = Enum.KeyCode.ButtonX



prompt:SetAttribute("InteractionId", "gate\_prism\_left")

prompt:SetAttribute("PromptTheme", "coop")



prompt.Parent = attachment

```



\### 권장값



| 속성 | 권장값 | 의미 |

|---|---:|---|

| `Style` | `Custom` | Roblox 기본 UI를 숨김 |

| `HoldDuration` | 0.4\~0.8초 | 짧고 명확한 홀드 행동 |

| `MaxActivationDistance` | 6\~10 studs | 대상 가까이에서만 실행 |

| `MaxIndicatorDistance` | 14\~20 studs | 멀리서도 상호작용 대상 인지 |

| `ClickablePrompt` | `true` | 모바일·마우스 입력 보조 |

| `RequiresLineOfSight` | 보통 `false` | 장식물에 UI가 가려지는 문제 방지 |



`Style = Custom`이면 기본 UI는 전혀 표시되지 않습니다. 표시와 입력을 만들지 않으면 특히 모바일에서 플레이어가 상호작용할 방법이 사라집니다. \[create.roblox](https://create.roblox.com/docs/reference/engine/classes/ProximityPrompt/Style)



\## 2. UI 템플릿



`StarterGui`에 다음을 만드세요.



```text

StarterGui

└─ PromptGui (ScreenGui)

&#x20;  ├─ PromptTemplate (BillboardGui) \[Enabled = false]

&#x20;  │  └─ Card (Frame)

&#x20;  │     ├─ Accent (Frame)

&#x20;  │     ├─ ObjectLabel (TextLabel)

&#x20;  │     ├─ ActionLabel (TextLabel)

&#x20;  │     ├─ KeyLabel (TextLabel)

&#x20;  │     ├─ HoldBar (Frame)

&#x20;  │     │  └─ Fill (Frame)

&#x20;  │     ├─ TouchButton (TextButton)

&#x20;  │     └─ TeamStatus (TextLabel)

&#x20;  └─ CustomPromptController (LocalScript)

```



\### 템플릿 설정



```text

PromptTemplate.Enabled = false

PromptTemplate.AlwaysOnTop = true

PromptTemplate.Size = 260 × 100

PromptTemplate.StudsOffset = (0, 2.5, 0)



Card:

AnchorPoint = (0.5, 0.5)

BackgroundTransparency = 0.10



HoldBar.Fill:

Size = UDim2.fromScale(0, 1)

Position = UDim2.fromScale(0, 0)

```



`BillboardGui`를 쓰면 3D 오브젝트 위에 프롬프트가 떠 보입니다. 상호작용 대상과 UI의 연결이 명확하므로 신호 패널·레버·스위치에 적합합니다.



\## 3. LocalScript 완성 예시



아래 코드는 커스텀 Prompt를 표시하고, 터치/마우스 홀드를 실제 Prompt 입력과 연결하며, 홀드 게이지를 애니메이션합니다.



```lua

\-- StarterGui/PromptGui/CustomPromptController.client.lua



local Players = game:GetService("Players")

local ProximityPromptService = game:GetService("ProximityPromptService")

local TweenService = game:GetService("TweenService")



local player = Players.LocalPlayer

local screenGui = script.Parent

local template = screenGui:WaitForChild("PromptTemplate")



local activeGuis = {}

local promptConnections = {}

local holdTweens = {}



local function addConnection(prompt, connection)

&#x20;   promptConnections\[prompt] = promptConnections\[prompt] or {}

&#x20;   table.insert(promptConnections\[prompt], connection)

end



local function clearConnections(prompt)

&#x20;   local list = promptConnections\[prompt]

&#x20;   if list then

&#x20;       for \_, connection in ipairs(list) do

&#x20;           connection:Disconnect()

&#x20;       end

&#x20;   end

&#x20;   promptConnections\[prompt] = nil

end



local function getAdornee(prompt)

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



local function keyText(prompt, inputType)

&#x20;   if inputType == Enum.ProximityPromptInputType.Touch then

&#x20;       return "탭하고 누르기"

&#x20;   end



&#x20;   if inputType == Enum.ProximityPromptInputType.Gamepad then

&#x20;       return "✕ 길게 누르기"

&#x20;   end



&#x20;   return prompt.KeyboardKeyCode.Name .. " 길게 누르기"

end



local function stopHoldTween(prompt, reset)

&#x20;   local tween = holdTweens\[prompt]



&#x20;   if tween then

&#x20;       tween:Cancel()

&#x20;       holdTweens\[prompt] = nil

&#x20;   end



&#x20;   local gui = activeGuis\[prompt]

&#x20;   if not gui then

&#x20;       return

&#x20;   end



&#x20;   local fill = gui.Card.HoldBar.Fill



&#x20;   if reset then

&#x20;       TweenService:Create(

&#x20;           fill,

&#x20;           TweenInfo.new(0.12, Enum.EasingStyle.Quad, Enum.EasingDirection.Out),

&#x20;           {Size = UDim2.fromScale(0, 1)}

&#x20;       ):Play()

&#x20;   end

end



local function startHoldTween(prompt)

&#x20;   if prompt.HoldDuration <= 0 then

&#x20;       return

&#x20;   end



&#x20;   stopHoldTween(prompt, false)



&#x20;   local gui = activeGuis\[prompt]

&#x20;   if not gui then

&#x20;       return

&#x20;   end



&#x20;   local fill = gui.Card.HoldBar.Fill

&#x20;   fill.Size = UDim2.fromScale(0, 1)



&#x20;   local tween = TweenService:Create(

&#x20;       fill,

&#x20;       TweenInfo.new(prompt.HoldDuration, Enum.EasingStyle.Linear),

&#x20;       {Size = UDim2.fromScale(1, 1)}

&#x20;   )



&#x20;   holdTweens\[prompt] = tween

&#x20;   tween:Play()

end



local function createPromptGui(prompt, inputType)

&#x20;   if activeGuis\[prompt] then

&#x20;       return

&#x20;   end



&#x20;   local adornee = getAdornee(prompt)

&#x20;   if not adornee then

&#x20;       return

&#x20;   end



&#x20;   local gui = template:Clone()

&#x20;   gui.Name = "Prompt\_" .. prompt:GetDebugId()

&#x20;   gui.Adornee = adornee

&#x20;   gui.Enabled = true

&#x20;   gui.Parent = screenGui



&#x20;   gui.Card.ObjectLabel.Text = prompt.ObjectText

&#x20;   gui.Card.ActionLabel.Text = prompt.ActionText

&#x20;   gui.Card.KeyLabel.Text = keyText(prompt, inputType)

&#x20;   gui.Card.HoldBar.Fill.Size = UDim2.fromScale(0, 1)



&#x20;   local slot = prompt:GetAttribute("TeamSlot")

&#x20;   gui.Card.TeamStatus.Text = slot == "left" and "왼쪽 신호 담당"

&#x20;       or slot == "right" and "오른쪽 신호 담당"

&#x20;       or ""



&#x20;   activeGuis\[prompt] = gui



&#x20;   local card = gui.Card

&#x20;   card.GroupTransparency = 1

&#x20;   card.Size = UDim2.fromScale(0.9, 0.9)



&#x20;   TweenService:Create(

&#x20;       card,

&#x20;       TweenInfo.new(0.18, Enum.EasingStyle.Quad, Enum.EasingDirection.Out),

&#x20;       {

&#x20;           GroupTransparency = 0,

&#x20;           Size = UDim2.fromScale(1, 1),

&#x20;       }

&#x20;   ):Play()



&#x20;   -- Custom 스타일에서는 모바일/마우스 버튼 입력을 직접 Prompt에 연결.

&#x20;   local button = card.TouchButton

&#x20;   local holding = false



&#x20;   addConnection(prompt, button.InputBegan:Connect(function(input)

&#x20;       local supported =

&#x20;           input.UserInputType == Enum.UserInputType.Touch

&#x20;           or input.UserInputType == Enum.UserInputType.MouseButton1



&#x20;       if supported and not holding then

&#x20;           holding = true

&#x20;           prompt:InputHoldBegin()

&#x20;       end

&#x20;   end))



&#x20;   addConnection(prompt, button.InputEnded:Connect(function(input)

&#x20;       local supported =

&#x20;           input.UserInputType == Enum.UserInputType.Touch

&#x20;           or input.UserInputType == Enum.UserInputType.MouseButton1



&#x20;       if supported and holding then

&#x20;           holding = false

&#x20;           prompt:InputHoldEnd()

&#x20;       end

&#x20;   end))

end



local function destroyPromptGui(prompt)

&#x20;   stopHoldTween(prompt, false)

&#x20;   clearConnections(prompt)



&#x20;   local gui = activeGuis\[prompt]

&#x20;   activeGuis\[prompt] = nil



&#x20;   if not gui then

&#x20;       return

&#x20;   end



&#x20;   local card = gui.Card



&#x20;   local tween = TweenService:Create(

&#x20;       card,

&#x20;       TweenInfo.new(0.14, Enum.EasingStyle.Quad, Enum.EasingDirection.In),

&#x20;       {

&#x20;           GroupTransparency = 1,

&#x20;           Size = UDim2.fromScale(0.9, 0.9),

&#x20;       }

&#x20;   )



&#x20;   tween.Completed:Once(function()

&#x20;       gui:Destroy()

&#x20;   end)



&#x20;   tween:Play()

end



ProximityPromptService.PromptShown:Connect(function(prompt, inputType)

&#x20;   if prompt.Style == Enum.ProximityPromptStyle.Custom then

&#x20;       createPromptGui(prompt, inputType)

&#x20;   end

end)



ProximityPromptService.PromptHidden:Connect(function(prompt)

&#x20;   destroyPromptGui(prompt)

end)



ProximityPromptService.PromptButtonHoldBegan:Connect(function(prompt)

&#x20;   startHoldTween(prompt)

end)



ProximityPromptService.PromptButtonHoldEnded:Connect(function(prompt)

&#x20;   stopHoldTween(prompt, true)

end)



ProximityPromptService.PromptTriggered:Connect(function(prompt)

&#x20;   local gui = activeGuis\[prompt]

&#x20;   if not gui then

&#x20;       return

&#x20;   end



&#x20;   stopHoldTween(prompt, false)

&#x20;   gui.Card.HoldBar.Fill.Size = UDim2.fromScale(1, 1)

&#x20;   gui.Card.Accent.BackgroundColor3 = Color3.fromRGB(38, 218, 181)

end)

```



커스텀 GUI 버튼에서 `InputHoldBegin()`을 호출하면 Roblox Prompt의 홀드 상태가 시작되고, 버튼에서 손을 떼면 `InputHoldEnd()`로 취소됩니다. 이 두 메서드는 특히 자체 Prompt GUI 버튼에서 실제 Prompt 입력을 시작·종료시키기 위해 제공됩니다. \[create.roblox](https://create.roblox.com/docs/reference/engine/classes/ProximityPrompt/Style)



\## 4. 서버 검증



LocalScript의 `PromptTriggered`는 연출용으로 쓸 수 있지만, 진도와 보상은 서버에서 처리합니다.



```lua

\-- ServerScriptService/PromptRouter.server.lua



local ProximityPromptService = game:GetService("ProximityPromptService")



local PlayerStateService = require(script.Parent.PlayerStateService)

local GateService = require(script.Parent.GateService)

local RewardService = require(script.Parent.RewardService)



ProximityPromptService.PromptTriggered:Connect(function(prompt, player)

&#x20;   local id = prompt:GetAttribute("InteractionId")



&#x20;   if id \~= "gate\_prism\_left" then

&#x20;       return

&#x20;   end



&#x20;   if PlayerStateService:getState(player) \~= "COOP\_SIGNAL\_3" then

&#x20;       return

&#x20;   end



&#x20;   if not GateService:isPlayerNearPrompt(player, prompt, 10) then

&#x20;       return

&#x20;   end



&#x20;   local result = GateService:markReady(player, "left")



&#x20;   if result == "success" then

&#x20;       GateService:openGateForTeam(player)

&#x20;       RewardService:grantGateProgressOnce(player)

&#x20;   end

end)

```



서버에서는 최소한 현재 퀘스트 단계, 실제 거리, 중복 처리 여부, 협동 시간 창을 검증해야 합니다. UI Tween이 끝났다는 이유만으로 보상을 주면 클라이언트 변조·중복 입력·네트워크 상태에서 문제가 생길 수 있습니다.



\## 5. 수학마을 적용



\### 협동 프리즘 스위치



```text

기본:

프리즘 스위치

\[ E 길게 누르기 ]



홀드 중:

신호 충전 중…

████████░░░░░░



준비 완료:

나: 준비됨

팀원: 반대편 신호로 이동 중



성공:

연결!

두 빛줄기가 게이트로 합쳐짐

```



\### 경사 조절 콘솔



```text

기본:

경사 콘솔

\[ 탭해서 조절 ]



선택 후:

열차가 목표보다 낮게 도착



동적 피드백:

“목표보다 낮게 도착했어.”

\[경사 다시 조절하기]



Custom Prompt:

경사 수치 + 위/아래 조절 + 목표 높이 미리보기

```



\## 주의할 점



| 실수 | 문제 | 해결 |

|---|---|---|

| `Style = Custom`만 설정 | 기본 UI가 사라져 상호작용 불가 | `PromptShown`에서 UI 생성 |

| `Activated`만 사용 | 홀드 중 취소·게이지가 부정확 | `InputBegan`/`InputEnded` 사용 |

| Tween 완료 시 보상 | 조작·프레임 드롭·중복 지급 위험 | 서버 `PromptTriggered` 검증 |

| 모든 Prompt를 Custom으로 변환 | 입력·접근성·QA 비용 폭증 | 협동/핵심 장치에만 적용 |

| `PromptHidden`에서 정리 안 함 | UI·이벤트 연결 누적 | GUI 파괴, Tween 취소, 연결 해제 |

| 색만으로 진행 표시 | 접근성 저하 | 게이지+문구+아이콘+월드 효과 병행 |

| 모바일을 뒤늦게 테스트 | 버튼이 눌리지 않거나 겹침 | 최초부터 `InputHoldBegin/End` 구현 |



\## 테스트 체크리스트



```text

\[표시]

\- 활성 거리 안에서만 커스텀 UI가 보인다.

\- 거리 밖으로 나가면 GUI, Tween, 이벤트 연결이 제거된다.

\- 동시에 두 Prompt가 보일 때 우선순위가 관리된다.



\[입력]

\- PC: E 키 홀드로 완료된다.

\- 게임패드: ButtonX 홀드로 완료된다.

\- 모바일: 버튼을 누르고 유지하면 완료된다.

\- 마우스: 클릭 유지로 완료된다.

\- 중간에 손을 떼면 게이지가 즉시 취소되고 0으로 복귀한다.



\[서버]

\- 거리 밖에서 요청해도 보상이 지급되지 않는다.

\- 잘못된 퀘스트 상태에서는 성공 처리되지 않는다.

\- 연타해도 같은 보상은 한 번만 지급된다.

\- 팀원 이탈 시 NPC 대체 또는 상태 복구가 된다.



\[UX]

\- 작은 모바일에서 기본 이동/점프 버튼과 겹치지 않는다.

\- 버튼과 텍스트가 긴 번역에서도 잘리지 않는다.

\- 색·소리를 꺼도 문구·게이지로 상태를 알 수 있다.

```



\## 결론



커스텀 Prompt는 다음 네 가지를 빠짐없이 구현해야 합니다.



```text

표시: PromptShown → GUI 생성

입력: InputHoldBegin / InputHoldEnd

진행도: PromptButtonHoldBegan / PromptButtonHoldEnded → Tween

결과: 서버 PromptTriggered → 상태·보상 확정

```



처음에는 \*\*협동 프리즘 스위치 하나\*\*만 `Style = Custom`으로 구현해 PC·모바일·게임패드에서 안정적으로 동작하는지 검증하세요. 그 뒤 경사 콘솔, 시민권 발급기처럼 “팀 상태·진행도·수학 피드백”을 보여 줘야 하는 오브젝트에만 확장하는 방식이 가장 안전합니다.

