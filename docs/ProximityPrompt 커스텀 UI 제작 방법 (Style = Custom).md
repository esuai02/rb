`Style = Custom`은 Roblox의 기본 ProximityPrompt UI를 완전히 끄고, **표시·키/터치 입력·홀드 진행·숨김·애니메이션을 직접 구현하는 방식**입니다. 수학마을에서는 협동 프리즘 스위치, 경사 레버, 시민권 발급기처럼 기본 Prompt로 표현하기 부족한 핵심 인터랙션에만 쓰는 것을 권장합니다.

Roblox 공식 문서상 Custom 스타일에서는 기본 UI가 제공되지 않으므로, `LocalScript`에서 `PromptShown`/`PromptHidden`을 구독해 UI를 생성·제거해야 합니다. 홀드 게이지는 `PromptButtonHoldBegan`/`PromptButtonHoldEnded`와 `HoldDuration`을 활용하고, 커스텀 버튼에서 실제 Prompt 입력을 시작·종료하려면 `InputHoldBegin()`과 `InputHoldEnd()`를 호출합니다. [create.roblox](https://create.roblox.com/docs/en-us/reference/engine/classes/ProximityPrompt.md)

## 동작 원리

```text
서버/Studio:
ProximityPrompt.Style = Custom
  ↓
클라이언트:
PromptShown 이벤트
  ↓
커스텀 UI 생성
  ↓
플레이어가 키/게임패드/터치 버튼을 누름
  ↓
prompt:InputHoldBegin()
  ↓
HoldDuration 동안 프로그레스 애니메이션
  ↓
prompt:InputHoldEnd()
  ↓
서버:
PromptTriggered 이벤트 수신
  ↓
서버 검증 후 월드 상태·보상·피드백 처리
```

Custom Prompt의 UI는 **클라이언트 전용 표현**이고, 보상·퀘스트·자격증·시민권 같은 게임 결과는 반드시 서버가 확정해야 합니다.

## 언제 Custom을 쓸까

| 상호작용 | 권장 스타일 | 이유 |
|---|---|---|
| 신호 패널 켜기 | Default | 단순하고 플랫폼 입력을 자동 처리 |
| NPC 도움 요청 | Default | 빠른 온보딩, 구현 부담 최소 |
| 포털 이동 | Default | 기본 UI로 충분 |
| 경사 레버 조절 | Custom | 현재 값, 변화 방향, 결과 미리보기 필요 |
| 협동 프리즘 스위치 | Custom | 홀드 원형 게이지, 팀원 준비 상태 필요 |
| 게이트 시민권 발급 | Custom | 자격 조건·발급 연출·진행도 표현 필요 |
| 보스/이벤트 장치 | Custom | 큰 시각 효과·여러 단계 상태 필요 |

MVP에서는 기본 Prompt를 유지하고, 실제 플레이에서 “협동 준비 상태를 플레이어가 이해하지 못한다”는 문제가 나온 곳만 Custom으로 바꾸는 편이 좋습니다.

## Studio 설정

### 1. Prompt 배치

`ProximityPrompt`는 `BasePart`, `Attachment`, 또는 `PrimaryPart`가 설정된 `Model` 아래에 둡니다.

```text
Workspace
└─ MathVillage
   └─ PrismSwitchLeft
      ├─ Attachment
      │  └─ ProximityPrompt
      └─ Highlight
```

### 2. Prompt 속성

협동 프리즘 스위치 예시입니다.

```lua
-- ServerScriptService/SetupPrismPrompt.server.lua
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

prompt:SetAttribute("InteractionId", "gate_prism_left")
prompt:SetAttribute("PromptTheme", "coop")
prompt:SetAttribute("TeamSlot", "left")

prompt.Parent = attachment
```

### 권장 속성값

| 속성 | 협동 스위치 권장 | 이유 |
|---|---:|---|
| `Style` | `Custom` | 준비 상태·홀드 게이지·팀 UI를 직접 표현 |
| `HoldDuration` | 0.4~0.8초 | “준비” 행동 감각은 주되 피로는 줄임 |
| `MaxActivationDistance` | 6~8 studs | 스위치에 실제로 접근해야 역할이 명확 |
| `MaxIndicatorDistance` | 14~18 studs | 가까이 가기 전에도 역할 대상 인지 |
| `RequiresLineOfSight` | `false` | 장식물에 가려 UI가 사라지는 문제 방지 |
| `ClickablePrompt` | `true` | 마우스·터치 모두에서 직접 누르기 지원 |
| `KeyboardKeyCode` | `E` | PC 사용자가 익숙한 기본 상호작용 키 |
| `GamepadKeyCode` | `ButtonX` | 게임패드 기본 상호작용 힌트 |

`HoldDuration`이 0이면 즉시 트리거되고, 0보다 큰 경우 해당 시간 동안 입력을 유지해야 실행됩니다. Custom UI에서 이 시간은 직접 게이지로 표현해야 합니다. [create.roblox](https://create.roblox.com/docs/en-us/ui/proximity-prompts.md)

## UI 계층 만들기

`StarterGui`에 아래 구조를 만드세요.

```text
StarterGui
└─ CustomPromptGui (ScreenGui)
   ├─ PromptTemplate (BillboardGui)
   │  └─ Card (Frame)
   │     ├─ Icon (ImageLabel)
   │     ├─ ObjectText (TextLabel)
   │     ├─ ActionText (TextLabel)
   │     ├─ KeyHint (TextLabel)
   │     ├─ HoldRing (Frame)
   │     │  └─ Fill (Frame)
   │     ├─ TeamStatus (TextLabel)
   │     └─ TouchButton (TextButton)
   └─ CustomPromptController (LocalScript)
```

### UI 권장값

- `PromptTemplate.Enabled = false`
- `PromptTemplate.AlwaysOnTop = true`
- `PromptTemplate.Size = UDim2.fromOffset(260, 96)`
- `PromptTemplate.StudsOffset = Vector3.new(0, 2.5, 0)`
- `Card.AnchorPoint = Vector2.new(0.5, 0.5)`
- `Card.BackgroundTransparency = 0.12`
- 모바일 텍스트는 자동 줄바꿈을 켜되, 문구 길이는 짧게 유지
- 실제 원형 홀드 게이지는 이미지 마스킹 또는 UIGradient 회전으로 만들 수 있지만, MVP는 가로 `Fill` 바로 시작해도 충분합니다

## 전체 LocalScript 예시

아래 코드는 다음을 처리합니다.

- `Style = Custom` Prompt가 보이면 BillboardGui 생성
- 텍스트·키 힌트·팀 상태 반영
- 키보드/게임패드 Prompt 이벤트와 홀드 게이지 동기화
- 터치/마우스 버튼 입력을 `InputHoldBegin`/`InputHoldEnd`로 연결
- Prompt가 숨겨지면 UI·연결·Tween 제거

```lua
-- StarterGui/CustomPromptGui/CustomPromptController.client.lua

local Players = game:GetService("Players")
local ProximityPromptService = game:GetService("ProximityPromptService")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")

local screenGui = script.Parent
local template = screenGui:WaitForChild("PromptTemplate")

local active = {}
local connections = {}

local function disconnectAll(prompt)
    local promptConnections = connections[prompt]
    if not promptConnections then
        return
    end

    for _, connection in ipairs(promptConnections) do
        connection:Disconnect()
    end

    connections[prompt] = nil
end

local function addConnection(prompt, connection)
    connections[prompt] = connections[prompt] or {}
    table.insert(connections[prompt], connection)
end

local function getAdornee(prompt)
    local parent = prompt.Parent

    if parent:IsA("Attachment") then
        return parent.Parent
    end

    if parent:IsA("BasePart") then
        return parent
    end

    if parent:IsA("Model") then
        return parent.PrimaryPart
    end

    return nil
end

local function getKeyText(prompt, inputType)
    if inputType == Enum.ProximityPromptInputType.Touch then
        return "탭"
    end

    if inputType == Enum.ProximityPromptInputType.Gamepad then
        return "✕"
    end

    if prompt.KeyboardKeyCode ~= Enum.KeyCode.Unknown then
        return prompt.KeyboardKeyCode.Name
    end

    return "E"
end

local function getTheme(prompt)
    local theme = prompt:GetAttribute("PromptTheme")

    if theme == "coop" then
        return {
            accent = Color3.fromRGB(106, 189, 255),
            icon = "rbxassetid://0",
        }
    end

    if theme == "math" then
        return {
            accent = Color3.fromRGB(255, 205, 79),
            icon = "rbxassetid://0",
        }
    end

    return {
        accent = Color3.fromRGB(38, 218, 181),
        icon = "rbxassetid://0",
    }
end

local function stopHold(gui)
    local tween = gui:GetAttribute("HoldTween")
    if tween then
        tween:Cancel()
    end

    gui.HoldRing.Fill.Size = UDim2.fromScale(0, 1)
end

local function startHold(prompt, gui)
    if prompt.HoldDuration <= 0 then
        return
    end

    stopHold(gui)

    local tween = TweenService:Create(
        gui.HoldRing.Fill,
        TweenInfo.new(prompt.HoldDuration, Enum.EasingStyle.Linear),
        { Size = UDim2.fromScale(1, 1) }
    )

    gui:SetAttribute("HoldTween", tween)
    tween:Play()
end

local function createPrompt(prompt, inputType)
    if active[prompt] then
        return
    end

    local adornee = getAdornee(prompt)
    if not adornee then
        return
    end

    local gui = template:Clone()
    gui.Name = "CustomPrompt_" .. prompt:GetDebugId()
    gui.Adornee = adornee
    gui.Enabled = true
    gui.Parent = screenGui

    local card = gui:WaitForChild("Card")
    local objectText = card:WaitForChild("ObjectText")
    local actionText = card:WaitForChild("ActionText")
    local keyHint = card:WaitForChild("KeyHint")
    local touchButton = card:WaitForChild("TouchButton")
    local teamStatus = card:WaitForChild("TeamStatus")
    local holdFill = card.HoldRing.Fill

    local theme = getTheme(prompt)

    objectText.Text = prompt.ObjectText
    actionText.Text = prompt.ActionText
    keyHint.Text = getKeyText(prompt, inputType)
    card.Accent.BackgroundColor3 = theme.accent

    local slot = prompt:GetAttribute("TeamSlot")
    if slot == "left" then
        teamStatus.Text = "왼쪽 신호 담당"
    elseif slot == "right" then
        teamStatus.Text = "오른쪽 신호 담당"
    else
        teamStatus.Text = ""
    end

    holdFill.Size = UDim2.fromScale(0, 1)
    touchButton.Visible = inputType == Enum.ProximityPromptInputType.Touch or prompt.ClickablePrompt
    active[prompt] = gui

    card.GroupTransparency = 1
    card.Size = UDim2.fromScale(0.92, 0.92)

    TweenService:Create(
        card,
        TweenInfo.new(0.18, Enum.EasingStyle.Quad, Enum.EasingDirection.Out),
        {
            GroupTransparency = 0,
            Size = UDim2.fromScale(1, 1),
        }
    ):Play()

    -- 터치/마우스용 직접 입력 처리
    local holding = false

    addConnection(prompt, touchButton.InputBegan:Connect(function(input)
        local isPress =
            input.UserInputType == Enum.UserInputType.Touch
            or input.UserInputType == Enum.UserInputType.MouseButton1

        if not isPress or holding then
            return
        end

        holding = true
        prompt:InputHoldBegin()
    end))

    addConnection(prompt, touchButton.InputEnded:Connect(function(input)
        local isRelease =
            input.UserInputType == Enum.UserInputType.Touch
            or input.UserInputType == Enum.UserInputType.MouseButton1

        if not isRelease or not holding then
            return
        end

        holding = false
        prompt:InputHoldEnd()
    end))

    addConnection(prompt, touchButton.AncestryChanged:Connect(function(_, parent)
        if not parent and holding then
            holding = false
            prompt:InputHoldEnd()
        end
    end))
end

local function destroyPrompt(prompt)
    local gui = active[prompt]
    if not gui then
        return
    end

    active[prompt] = nil
    disconnectAll(prompt)

    local card = gui:FindFirstChild("Card")
    if not card then
        gui:Destroy()
        return
    end

    local tween = TweenService:Create(
        card,
        TweenInfo.new(0.14, Enum.EasingStyle.Quad, Enum.EasingDirection.In),
        {
            GroupTransparency = 1,
            Size = UDim2.fromScale(0.92, 0.92),
        }
    )

    tween.Completed:Once(function()
        gui:Destroy()
    end)

    tween:Play()
end

ProximityPromptService.PromptShown:Connect(function(prompt, inputType)
    if prompt.Style ~= Enum.ProximityPromptStyle.Custom then
        return
    end

    createPrompt(prompt, inputType)
end)

ProximityPromptService.PromptHidden:Connect(function(prompt)
    destroyPrompt(prompt)
end)

ProximityPromptService.PromptButtonHoldBegan:Connect(function(prompt)
    local gui = active[prompt]
    if not gui then
        return
    end

    local card = gui:FindFirstChild("Card")
    if card then
        startHold(prompt, card)
    end
end)

ProximityPromptService.PromptButtonHoldEnded:Connect(function(prompt)
    local gui = active[prompt]
    if not gui then
        return
    end

    local card = gui:FindFirstChild("Card")
    if card then
        stopHold(card)
    end
end)

ProximityPromptService.PromptTriggered:Connect(function(prompt)
    local gui = active[prompt]
    if not gui then
        return
    end

    local card = gui:FindFirstChild("Card")
    if card then
        stopHold(card)
        card.Accent.BackgroundColor3 = Color3.fromRGB(38, 218, 181)
    end
end)
```

## 서버 처리

UI는 클라이언트에서 만들지만, 실제 성공 판정은 서버에서 해야 합니다. `PromptTriggered`를 서버에서 받아 퀘스트 상태, 거리, 중복 처리, 협동 조건을 검증합니다.

```lua
-- ServerScriptService/PromptRouter.server.lua

local ProximityPromptService = game:GetService("ProximityPromptService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local FeedbackEvent = ReplicatedStorage.Remotes.FeedbackEvent

local GateService = require(script.Parent.GateService)
local PlayerStateService = require(script.Parent.PlayerStateService)

ProximityPromptService.PromptTriggered:Connect(function(prompt, player)
    if prompt:GetAttribute("InteractionId") ~= "gate_prism_left" then
        return
    end

    if not GateService:isPlayerNearPrompt(player, prompt, 10) then
        return
    end

    if PlayerStateService:getState(player) ~= "COOP_SIGNAL_3" then
        return
    end

    local result = GateService:markCoopSwitchReady(player, "left")

    if result == "waiting" then
        FeedbackEvent:FireClient(player, {
            eventId = "coop_waiting",
            kind = "team",
            titleKey = "feedback.coop.waiting.title",
            bodyKey = "feedback.coop.waiting.body",
            duration = 2.5,
        })
    elseif result == "success" then
        GateService:openGateForTeam(player)

        FeedbackEvent:FireClient(player, {
            eventId = "coop_success",
            kind = "success",
            titleKey = "feedback.coop.success.title",
            bodyKey = "feedback.coop.success.body",
            progress = { current = 3, total = 3 },
            duration = 3,
        })
    end
end)
```

`ProximityPromptService`는 Prompt의 표시, 숨김, 홀드 시작/종료, 트리거 이벤트를 전역으로 처리할 수 있습니다. 서버에서는 이 이벤트를 게임 상태 전환의 시작점으로 쓰되, 모든 보상과 진도는 별도 상태 검증 뒤에 처리하세요. [create.roblox](https://create.roblox.com/docs/en-us/ui/proximity-prompts.md)

## 핵심 함정 6가지

### 1. `Style = Custom`만 설정하고 입력 처리를 안 함

가장 흔한 실패입니다. Custom으로 바꾸면 기본 UI가 사라지고, 특히 모바일에서 탭해도 아무 일도 일어나지 않을 수 있습니다.

**해결:** `TextButton.InputBegan`에서 `prompt:InputHoldBegin()`, `InputEnded`에서 `prompt:InputHoldEnd()`를 호출합니다. [create.roblox](https://create.roblox.com/docs/en-us/reference/engine/classes/ProximityPrompt.md)

### 2. `Activated`만 사용해 홀드가 깨짐

`TextButton.Activated`는 탭 완료에 적합하지만, `HoldDuration > 0`의 누르고 있는 상태·취소·진행 게이지와 정확히 연결하기 어렵습니다.

**해결:** 홀드 Prompt는 `InputBegan`/`InputEnded`로 처리합니다.

### 3. `PromptTriggered`에서 바로 보상 지급

Prompt를 빠르게 반복하거나 상태가 꼬이면 보상이 중복될 수 있습니다.

**해결:** 서버에서 다음을 확인합니다.

```text
- 현재 퀘스트 상태
- 실제 거리
- 동일 미션 완료 여부
- 팀원의 준비 상태
- 서버 시간 기준 허용 창
- 이미 보상이 지급됐는지
```

### 4. 모든 Prompt를 Custom으로 바꿈

Custom은 디자인 자유도가 크지만, 입력·터치·게임패드·현지화·접근성 QA 부담도 큽니다.

**해결:** 기본 Prompt는 유지하고, 팀 상태·게이지·특별 연출이 꼭 필요한 오브젝트에만 Custom을 적용합니다.

### 5. Prompt GUI를 숨길 때 연결을 해제하지 않음

Prompt가 자주 보였다 사라지는 월드에서는 이벤트 연결과 GUI가 누적되어 메모리·중복 입력 문제가 생길 수 있습니다.

**해결:** `PromptHidden`에서 GUI를 파괴하고 모든 `RBXScriptConnection`을 `Disconnect()`합니다.

### 6. UI가 월드와 분리됨

커스텀 카드만 화면에 뜨면 무슨 물체를 조작하는지 혼란스럽습니다.

**해결:** Prompt가 보일 때 동시에 대상에 다음을 적용합니다.

```text
- Highlight
- Outline
- 청록/노랑 점멸
- 약한 파티클
- 방향 빔
- 대상 위치로 카메라 보정
```

UI는 “무엇을 누를지”, 월드 연출은 “어디에서 왜 하는지”를 담당하게 하세요.

## 협동 프리즘 스위치 UI 예시

```text
           ┌────────────────────────────┐
           │      프리즘 스위치          │
           │                            │
           │    [ 청록 원형 홀드 게이지 ] │
           │                            │
           │       신호 준비             │
           │       E / 탭                │
           │                            │
           │  나: 준비 중                │
           │  팀원: 반대편 신호로 이동 중 │
           └────────────────────────────┘
```

상태 전환은 아래처럼 보이면 됩니다.

```text
기본:
“신호 준비”

홀드 중:
“신호 충전 중…”
게이지 0% → 100%

내가 준비됨:
“나: 준비됨”
카드 테두리 청록 점등

팀원 대기:
“팀원 신호를 기다리는 중”
월드 반대편에 방향 빔

둘 다 준비:
“연결!”
두 신호 빛줄기 합류 → 게이트 점등
```

## 접근성·현지화

Custom Prompt를 만들면 기본 UI가 제공하던 편의도 직접 책임져야 합니다.

- 키 이름을 텍스트로만 쓰지 말고 기기 아이콘과 병행
- `ActionText`는 2~4단어의 행동 표현 유지
- `ObjectText`는 세계관 고유명보다 기능 중심으로 작성
- 색만으로 준비/성공/대기를 표시하지 않기
- 홀드 진행은 색 + 숫자/게이지 + 애니메이션으로 표현
- 텍스트 크기, 대비, 오디오·햅틱 설정을 고려
- 터치·마우스·키보드·게임패드에서 실제 테스트
- 긴 번역을 견딜 수 있도록 `AutomaticSize`, `UIListLayout`, `UIPadding`, `UISizeConstraint` 사용
- 아랍어 같은 RTL 언어의 정렬·아이콘 위치는 별도로 검수

Custom UI는 기본 Prompt가 자동으로 제공하던 입력 경험을 대체하므로, 모든 플랫폼에서 직접 입력 동작을 재현해야 합니다. Roblox는 `ProximityPrompt`의 입력 방식과 홀드 이벤트를 공식적으로 제공하지만, Custom 스타일에서는 이를 바탕으로 개발자가 UI를 구현합니다. [create.roblox](https://create.roblox.com/docs/en-us/reference/engine/classes/ProximityPrompt.md)

## 테스트 체크리스트

```text
[표시]
- Prompt가 활성 거리에서만 나타나는가
- PromptHidden 때 GUI와 이벤트 연결이 제거되는가
- 동시에 여러 Custom Prompt가 나타날 때 우선순위가 관리되는가

[입력]
- PC E키로 즉시/홀드 실행되는가
- 게임패드 ButtonX로 실행되는가
- 모바일 탭·홀드로 실행되는가
- 마우스 클릭·홀드로 실행되는가
- 홀드 중 손을 떼면 진행 게이지가 초기화되는가

[서버]
- 거리 밖에서 트리거해도 실패하는가
- 잘못된 퀘스트 상태에서는 보상이 지급되지 않는가
- 버튼 연타로 보상이 중복되지 않는가
- 팀원 이탈 시 NPC 대체가 작동하는가

[UX]
- 작은 모바일에서 조이스틱·점프 버튼과 겹치지 않는가
- 목표 오브젝트가 월드에서도 명확히 강조되는가
- 긴 번역문에서 카드·버튼이 깨지지 않는가
- 색·소리 없이도 의미를 이해할 수 있는가
```

## 결론

`Style = Custom`의 핵심은 예쁜 프롬프트를 만드는 것이 아니라, 기본 Prompt가 제공하던 기능을 빠짐없이 다시 만드는 것입니다.

```text
PromptShown / PromptHidden
→ UI 생성·제거

InputHoldBegin / InputHoldEnd
→ 터치·마우스·홀드 처리

PromptButtonHoldBegan / PromptButtonHoldEnded
→ 홀드 게이지 애니메이션

PromptTriggered
→ 서버 검증·상태 전환·보상

월드 Highlight + 동적 피드백
→ 플레이어가 결과와 다음 행동을 이해
```

수학마을에서는 모든 Prompt를 Custom으로 바꾸기보다, **협동 프리즘 스위치 하나를 완성도 높게 Custom으로 구현해 실제 플레이에서 효과를 검증한 뒤**, 경사 레버와 시민권 발급기 순으로 확장하는 접근이 가장 안전합니다.