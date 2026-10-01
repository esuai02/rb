 `HoldDuration` 홀드 게이지는 **Prompt의 실제 홀드 상태를 이벤트로 받고**, 게이지 UI는 `TweenService`로 `HoldDuration`과 정확히 같은 시간 동안 채우는 방식으로 구현합니다. 핵심은 트윈 완료를 성공 판정으로 쓰지 않는 것입니다. 성공은 오직 Roblox의 `PromptTriggered`와 서버 검증으로 확정해야 합니다.

Roblox에서 `HoldDuration > 0`이면 사용자가 해당 시간 동안 입력을 유지해야 Prompt가 트리거되며, 홀드 시작·종료는 `PromptButtonHoldBegan`과 `PromptButtonHoldEnded`로 받을 수 있습니다. UI 전환은 `TweenService`로 부드럽게 처리할 수 있습니다. [github](https://github.com/Roblox/creator-docs/blob/main/content/en-us/ui/proximity-prompts.md)

## 전체 흐름

```text
입력 시작
→ PromptButtonHoldBegan
→ 게이지 0% → 100% Tween 시작
→ 입력 유지
→ HoldDuration 충족
→ PromptTriggered
→ 서버가 상호작용 검증·결과 확정

입력 중단
→ PromptButtonHoldEnded
→ 진행 Tween 취소
→ 게이지 0%로 리셋
```

## Studio 설정

협동 프리즘 스위치 예시입니다.

```lua
local prompt = Instance.new("ProximityPrompt")

prompt.ActionText = "신호 준비"
prompt.ObjectText = "프리즘 스위치"
prompt.Style = Enum.ProximityPromptStyle.Custom

prompt.HoldDuration = 0.6
prompt.MaxActivationDistance = 8
prompt.MaxIndicatorDistance = 16
prompt.ClickablePrompt = true
prompt.RequiresLineOfSight = false

prompt.Parent = workspace.MathVillage.PrismSwitchLeft.Attachment
```

온보딩·모바일 기준으로는 0.4~0.8초가 적당합니다. 1초 이상 홀드는 반복 미션에서 피로하게 느껴질 수 있습니다.

## 가장 단순한 가로 게이지

### UI 구조

```text
BillboardGui
└─ Card
   ├─ ActionText       TextLabel
   ├─ HoldBar          Frame
   │  └─ Fill          Frame
   └─ TouchButton      TextButton
```

`Fill` 초기값:

```lua
Fill.Size = UDim2.fromScale(0, 1)
Fill.AnchorPoint = Vector2.new(0, 0)
Fill.Position = UDim2.fromScale(0, 0)
```

### HoldGauge 모듈

아래 모듈은 홀드 시작 시 게이지를 채우고, 중단 시 현재 Tween을 취소한 뒤 부드럽게 0으로 되돌립니다.

```lua
-- StarterPlayerScripts/HoldGauge.lua

local TweenService = game:GetService("TweenService")

local HoldGauge = {}
HoldGauge.__index = HoldGauge

function HoldGauge.new(fillFrame)
    local self = setmetatable({}, HoldGauge)

    self.fill = fillFrame
    self.activeTween = nil
    self.resetTween = nil
    self.isHolding = false

    self.fill.Size = UDim2.fromScale(0, 1)

    return self
end

function HoldGauge:_cancelTweens()
    if self.activeTween then
        self.activeTween:Cancel()
        self.activeTween = nil
    end

    if self.resetTween then
        self.resetTween:Cancel()
        self.resetTween = nil
    end
end

function HoldGauge:start(duration)
    self:_cancelTweens()

    if duration <= 0 then
        self.fill.Size = UDim2.fromScale(1, 1)
        return
    end

    self.isHolding = true
    self.fill.Size = UDim2.fromScale(0, 1)

    self.activeTween = TweenService:Create(
        self.fill,
        TweenInfo.new(duration, Enum.EasingStyle.Linear),
        {
            Size = UDim2.fromScale(1, 1),
        }
    )

    self.activeTween:Play()
end

function HoldGauge:stop()
    self.isHolding = false

    if self.activeTween then
        self.activeTween:Cancel()
        self.activeTween = nil
    end

    if self.fill.Size.X.Scale <= 0 then
        return
    end

    self.resetTween = TweenService:Create(
        self.fill,
        TweenInfo.new(0.12, Enum.EasingStyle.Quad, Enum.EasingDirection.Out),
        {
            Size = UDim2.fromScale(0, 1),
        }
    )

    self.resetTween:Play()
end

function HoldGauge:complete()
    self.isHolding = false

    if self.activeTween then
        self.activeTween:Cancel()
        self.activeTween = nil
    end

    if self.resetTween then
        self.resetTween:Cancel()
        self.resetTween = nil
    end

    self.fill.Size = UDim2.fromScale(1, 1)
end

function HoldGauge:destroy()
    self:_cancelTweens()
end

return HoldGauge
```

`Linear`는 보통 홀드 게이지에 적합합니다. 게이지의 채움 속도와 실제 `HoldDuration`이 시각적으로 일치해야 하기 때문입니다. 반면 카드 등장·사라짐에는 `Quad Out`, 버튼 눌림에는 `Back Out`처럼 더 자연스러운 easing을 써도 됩니다. Roblox의 `TweenService`는 `TweenInfo`를 통해 시간, easing style, direction을 제어합니다. [create.roblox](https://create.roblox.com/docs/ko-kr/ui/animation)

## Prompt 이벤트와 연결

### 전역 이벤트 방식

```lua
-- StarterPlayerScripts/CustomPromptController.client.lua

local ProximityPromptService = game:GetService("ProximityPromptService")

local HoldGauge = require(script.Parent.HoldGauge)

local activeGauges = {}

local function registerPrompt(prompt, fillFrame)
    activeGauges[prompt] = HoldGauge.new(fillFrame)
end

local function unregisterPrompt(prompt)
    local gauge = activeGauges[prompt]

    if gauge then
        gauge:destroy()
        activeGauges[prompt] = nil
    end
end

ProximityPromptService.PromptButtonHoldBegan:Connect(function(prompt)
    local gauge = activeGauges[prompt]

    if not gauge then
        return
    end

    gauge:start(prompt.HoldDuration)
end)

ProximityPromptService.PromptButtonHoldEnded:Connect(function(prompt)
    local gauge = activeGauges[prompt]

    if not gauge then
        return
    end

    gauge:stop()
end)

ProximityPromptService.PromptTriggered:Connect(function(prompt)
    local gauge = activeGauges[prompt]

    if not gauge then
        return
    end

    gauge:complete()
end)

ProximityPromptService.PromptHidden:Connect(function(prompt)
    unregisterPrompt(prompt)
end)
```

이 구조에서는 `PromptShown` 때 UI를 만들며 `registerPrompt(prompt, card.HoldBar.Fill)`을 호출하고, `PromptHidden` 때 GUI와 모듈을 함께 정리합니다.

`ProximityPromptService`는 Prompt별 스크립트를 붙이지 않고도 홀드 시작·종료·실행 이벤트를 전역적으로 받을 수 있어, 여러 스위치와 콘솔을 가진 수학마을에서 특히 유리합니다. [github](https://github.com/Roblox/creator-docs/blob/main/content/en-us/ui/proximity-prompts.md)

## 모바일 터치 홀드 처리

`Style = Custom`이면 기본 UI 입력 처리가 사라집니다. 따라서 `TextButton`에서 홀드 시작·종료를 Prompt에 직접 전달해야 합니다.

```lua
local function bindTouchButton(prompt, touchButton)
    local holding = false

    local beganConnection = touchButton.InputBegan:Connect(function(input)
        local supported =
            input.UserInputType == Enum.UserInputType.Touch
            or input.UserInputType == Enum.UserInputType.MouseButton1

        if not supported or holding then
            return
        end

        holding = true
        prompt:InputHoldBegin()
    end)

    local endedConnection = touchButton.InputEnded:Connect(function(input)
        local supported =
            input.UserInputType == Enum.UserInputType.Touch
            or input.UserInputType == Enum.UserInputType.MouseButton1

        if not supported or not holding then
            return
        end

        holding = false
        prompt:InputHoldEnd()
    end)

    return function()
        beganConnection:Disconnect()
        endedConnection:Disconnect()

        if holding then
            holding = false
            prompt:InputHoldEnd()
        end
    end
end
```

### 왜 `Activated`만 쓰면 부족한가

```lua
-- 홀드 구현에 부적합한 예
touchButton.Activated:Connect(function()
    prompt:InputHoldBegin()
    prompt:InputHoldEnd()
end)
```

`Activated`는 “입력이 완료됐다”는 시점에 가깝기 때문에, 누르는 동안의 진행도나 중간 취소를 제대로 표현하기 어렵습니다. 홀드 게이지는 `InputBegan`에서 시작하고 `InputEnded`에서 취소해야 합니다.

## 키보드와 게임패드

Custom Prompt에서도 Roblox가 `PromptButtonHoldBegan`/`PromptButtonHoldEnded` 이벤트를 발생시킬 수 있도록 Prompt의 키 설정을 유지하세요.

```lua
prompt.KeyboardKeyCode = Enum.KeyCode.E
prompt.GamepadKeyCode = Enum.KeyCode.ButtonX
```

커스텀 UI에는 현재 입력 방식에 맞는 힌트를 표시합니다.

```lua
local function keyHintFor(prompt, inputType)
    if inputType == Enum.ProximityPromptInputType.Touch then
        return "탭하고 누르기"
    end

    if inputType == Enum.ProximityPromptInputType.Gamepad then
        return "✕ 길게 누르기"
    end

    return prompt.KeyboardKeyCode.Name .. " 길게 누르기"
end
```

터치 버튼은 직접 `InputHoldBegin`/`InputHoldEnd`를 연결해야 하지만, 키보드·게임패드도 실제 기기에서 반드시 테스트하세요. 커스텀 스타일은 기본 Prompt가 제공하던 입력·접근성 동작을 개발자가 재현해야 하기 때문입니다. [github](https://github.com/Roblox/creator-docs/blob/main/content/en-us/ui/proximity-prompts.md)

## 원형 게이지로 확장하기

가로 게이지가 MVP에는 가장 안전합니다. 원형 게이지가 필요하다면 구현 방식은 세 가지입니다.

| 방식 | 장점 | 단점 | 권장 시점 |
|---|---|---|---|
| 가로 `Fill` Frame | 가장 단순, 안정적, 모바일에서 명확 | 시각적 임팩트 낮음 | MVP |
| 이미지 스프라이트 시트 | 네온·단청 스타일 표현 쉬움 | 프레임 에셋 제작 필요 | 아트 방향 확정 후 |
| 반원 2개 + `UIGradient` 회전 | 정교한 원형 진행 표현 | 구현 복잡·버그 가능성 | 핵심 협동 스위치만 |

### 실용적인 대안: 원형 테두리 + 가로 진행바

완전한 원형 채움 대신 다음처럼 만드세요.

```text
[원형 아이콘/테두리]
        신호 준비
██████████░░░░░░░░
```

- 원형 아이콘은 `ImageLabel`
- 테두리는 홀드 중 색·크기·투명도 Tween
- 실제 진행도는 가로 `Fill` Frame
- 접근성 측면에서 실제 진행률이 더 분명함

### 홀드 중 아이콘 펄스

```lua
local function startIconPulse(icon)
    local grow = TweenService:Create(
        icon,
        TweenInfo.new(0.25, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, -1, true),
        {
            Size = UDim2.fromScale(1.08, 1.08),
        }
    )

    grow:Play()
    return grow
end
```

홀드 시작 시 펄스를 시작하고, 홀드 종료·실행·숨김 때 `pulseTween:Cancel()`로 중지하세요.

## 완료 상태와 서버 판정 분리

다음은 하면 안 됩니다.

```lua
-- 잘못된 설계
gaugeTween.Completed:Connect(function()
    givePlayerCitizenBadge()
end)
```

Tween은 로컬 시각 효과일 뿐입니다. 프레임 드롭, UI 삭제, 네트워크 지연, 클라이언트 변조 상황에서 실제 게임 결과를 보장하지 않습니다.

올바른 구조입니다.

```text
클라이언트:
게이지를 HoldDuration 동안 채움

Roblox Prompt:
HoldDuration 충족 후 PromptTriggered

서버:
거리·퀘스트·쿨다운·팀 조건 검증
→ 실제 게이트 신호 활성화
→ 보상 지급
→ FeedbackEvent 발송

클라이언트:
성공 연출 및 게이지 완료 상태 표현
```

`PromptTriggered`는 `HoldDuration`이 0이 아닌 Prompt에서 요구 시간이 충족된 후 발생합니다. 그러나 보상과 진도는 여전히 서버 측 상태 검증을 거쳐야 합니다. [github](https://github.com/Roblox/creator-docs/blob/main/content/en-us/ui/proximity-prompts.md)

## 취소와 연타 처리

### 취소 시

```text
입력 시작
→ 게이지 40%
→ 손가락/키를 뗌
→ activeTween:Cancel()
→ 0.12초 안에 게이지 0% 복귀
→ 월드 스위치도 준비 상태 취소
```

### 연타 시

```text
첫 홀드 시작
→ 기존 Tween 취소
→ 게이지 0%에서 다시 시작
→ 완료 전에는 서버 보상 없음
→ 성공 뒤에는 Prompt.Enabled = false 또는 쿨다운
```

서버에는 별도의 쿨다운도 두세요.

```lua
local lastTriggered = {}

local function canTrigger(player, interactionId)
    local key = tostring(player.UserId) .. ":" .. interactionId
    local now = os.clock()

    if lastTriggered[key] and now - lastTriggered[key] < 0.5 then
        return false
    end

    lastTriggered[key] = now
    return true
end
```

이는 보안의 전부가 아니라 중복 이벤트를 줄이는 보조 장치입니다. 실제로는 퀘스트 상태와 완료 여부 검증이 핵심입니다.

## 협동 홀드 게이지

수학마을의 프리즘 스위치에는 플레이어 본인 게이지와 팀 상태를 분리해 보여 주세요.

```text
프리즘 스위치

나:
████████████████  준비 완료

팀원:
████████░░░░░░░░  신호 이동 중

조건:
두 신호가 3초 안에 준비되면 연결됩니다.
```

### 상태별 색상

| 상태 | 게이지 | 문구 | 월드 연출 |
|---|---|---|---|
| 대기 | 회색 0% | `신호 준비` | 약한 외곽선 |
| 홀드 중 | 노랑 진행 | `신호 충전 중…` | 레버 빛 증가 |
| 내 준비 완료 | 청록 100% | `팀원 신호 대기 중` | 내 빛 기둥 유지 |
| 팀 동기화 성공 | 청록/금색 | `연결!` | 두 빛줄기 합류 |
| 중단 | 보라/회색 0% | `다시 준비할 수 있어` | 부드럽게 감광 |
| 팀원 이탈 | 청록 + 드론 | `보조 드론 연결 중` | NPC가 반대편 이동 |

색만 사용하지 말고 문구·아이콘·게이지 위치 변화도 함께 쓰세요.

## 자동 QA

```text
H01: HoldDuration=0이면 게이지를 표시하지 않거나 즉시 완료 상태가 된다.
H02: 홀드 시작 시 게이지가 0%에서 시작한다.
H03: 게이지 Tween 시간은 prompt.HoldDuration과 같다.
H04: 홀드 중 입력을 떼면 Tween이 즉시 취소된다.
H05: 취소 뒤 0.2초 이내 게이지가 0%로 돌아간다.
H06: 홀드 성공 뒤 PromptTriggered 전에 보상이 지급되지 않는다.
H07: PromptTriggered가 서버 검증을 통과할 때만 보상·진도가 변한다.
H08: 홀드 성공 후 게이지가 완료 상태로 보이고 다음 Prompt로 전환된다.
H09: 모바일 터치 홀드, PC 키 홀드, 게임패드 버튼 홀드가 모두 동작한다.
H10: PromptHidden 시 Tween·펄스·입력 연결이 모두 정리된다.
H11: 홀드 중 팀원이 나가면 게이지/팀 상태가 NPC 대체로 전환된다.
H12: 작은 모바일 화면에서 게이지가 이동·점프 버튼과 겹치지 않는다.
```

## 구현 순서

1. 기본 `ProximityPrompt`에 `HoldDuration = 0.6`을 설정합니다.  
2. Custom UI의 가로 `Fill` 게이지부터 만듭니다.  
3. `PromptButtonHoldBegan`에서 `TweenService` 채움 애니메이션을 시작합니다.  
4. `PromptButtonHoldEnded`에서 Tween을 취소하고 빠르게 0으로 되돌립니다.  
5. `PromptTriggered`에서만 완료 연출을 실행합니다.  
6. 서버의 `PromptTriggered`에서 실제 상태·보상·진도를 검증합니다.  
7. 모바일 `TextButton`에 `InputHoldBegin`/`InputHoldEnd`를 연결합니다.  
8. 이후 협동 상태, 원형 장식, 사운드·햅틱, 접근성 옵션을 추가합니다.  

## 결론

HoldDuration 게이지의 핵심 공식은 다음입니다.

```text
PromptButtonHoldBegan
→ Tween(0% → 100%, HoldDuration)

PromptButtonHoldEnded
→ Cancel Tween
→ Tween(현재값 → 0%, 0.12초)

PromptTriggered
→ 서버 검증
→ 성공 연출·다음 상태
```

즉, **Tween은 플레이어에게 “얼마나 더 누르면 되는지”를 보여 주는 시각적 약속이고, `PromptTriggered + 서버 검증`만이 실제 성공을 결정**합니다.
