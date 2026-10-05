--!strict
-- 화면은 현재 목표 하나만 보여 준다 (K5). 판정은 서버가 하고 클라이언트는 고른 것만 보낸다 (INV-4).
-- 글자는 모두 번역표를 거친다 — 코드에는 키만 쓴다 (INV-3). 색만으로 뜻을 전하지 않는다 (INV-9).
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Text = require(ReplicatedStorage.Shared.Text)
local Layout = require(ReplicatedStorage.Shared.Layout)

local SignalRemote = ReplicatedStorage:WaitForChild("SignalRemote")
local SlopeRemote = ReplicatedStorage:WaitForChild("SlopeRemote")
local ResultRemote = ReplicatedStorage:WaitForChild("ResultRemote")

local STAGE_PANEL, STAGE_COORDINATE, STAGE_SLOPE, STAGE_PORTAL = "panel", "coordinate", "slope", "portal"
local HINT_IDLE_SECONDS = 10   -- 정본 값 cv.hint_ladder.first_trigger.idle_seconds

local stage = STAGE_PANEL
local cursorX, cursorY = 0, 0
local hintLevel, attempts, lastActed = 0, 0, os.clock()

local screen = Instance.new("ScreenGui")
screen.Name = "GateHud"
screen.ResetOnSpawn = false
screen.Parent = Players.LocalPlayer:WaitForChild("PlayerGui")   -- 화면에 그려지는 곳은 PlayerGui 뿐이다

local function panel(name: string, position: UDim2, size: UDim2): Frame
	local frame = Instance.new("Frame")
	frame.Name = name
	frame.Position = position
	frame.Size = size
	frame.BackgroundTransparency = 0.3
	frame.Parent = screen
	return frame
end

local function label(name: string, parent: Instance, position: UDim2, size: UDim2): TextLabel
	local item = Instance.new("TextLabel")
	item.Name = name
	item.Position = position
	item.Size = size
	item.TextScaled = true
	item.TextWrapped = true
	item.BackgroundTransparency = 1
	item.Parent = parent
	return item
end

local function button(name: string, parent: Instance, position: UDim2): TextButton
	local item = Instance.new("TextButton")
	item.Name = name
	item.Position = position
	item.Size = UDim2.new(0, 150, 0, 40)
	item.TextScaled = true
	item.Parent = parent
	return item
end

local top = panel("Top", UDim2.new(0, 16, 0, 16), UDim2.new(0, 460, 0, 120))
local goal = label("Goal", top, UDim2.new(0, 8, 0, 4), UDim2.new(1, -16, 0, 34))
local situation = label("Situation", top, UDim2.new(0, 8, 0, 40), UDim2.new(1, -16, 0, 34))
local response = label("Response", top, UDim2.new(0, 8, 0, 76), UDim2.new(1, -16, 0, 34))

local hintBox = panel("Hint", UDim2.new(0, 16, 0, 148), UDim2.new(0, 460, 0, 56))
local hint = label("HintText", hintBox, UDim2.new(0, 8, 0, 4), UDim2.new(1, -16, 1, -8))

local labelBox = panel("Discovery", UDim2.new(0, 16, 0, 212), UDim2.new(0, 460, 0, 96))
local discovery = label("DiscoveryText", labelBox, UDim2.new(0, 8, 0, 4), UDim2.new(1, -16, 0, 52))
local useLabel = button("UseLabel", labelBox, UDim2.new(0, 8, 0, 56))

local moves = panel("Moves", UDim2.new(0, 16, 1, -200), UDim2.new(0, 330, 0, 184))
local moveRight = button("MoveRight", moves, UDim2.new(0, 170, 0, 70))
local moveLeft = button("MoveLeft", moves, UDim2.new(0, 8, 0, 70))
local moveUp = button("MoveUp", moves, UDim2.new(0, 90, 0, 20))
local moveDown = button("MoveDown", moves, UDim2.new(0, 90, 0, 124))

local slopes = panel("Slopes", UDim2.new(0, 360, 1, -200), UDim2.new(0, 170, 0, 184))
local slopeUp = button("SlopeUp", slopes, UDim2.new(0, 8, 0, 12))
local slopeDown = button("SlopeDown", slopes, UDim2.new(0, 8, 0, 64))
local slopeFlat = button("SlopeFlat", slopes, UDim2.new(0, 8, 0, 116))

-- 버튼 글자는 한 번만 넣는다 — 키는 글자 그대로 적어 검사할 수 있게 한다
moveRight.Text = Text.get("action.position.move_right")
moveLeft.Text = Text.get("action.position.move_left")
moveUp.Text = Text.get("action.position.move_up")
moveDown.Text = Text.get("action.position.move_down")
slopeUp.Text = Text.get("action.slope.increase")
slopeDown.Text = Text.get("action.slope.decrease")
slopeFlat.Text = Text.get("action.slope.set_zero")
useLabel.Text = Text.get("choice.use_label")

local function showStage()
	moves.Visible = stage == STAGE_COORDINATE
	slopes.Visible = stage == STAGE_SLOPE
	hintBox.Visible = false
	if stage == STAGE_PANEL then
		goal.Text = Text.get("goal.signal_1")
		situation.Text = Text.get("sit.gate_dark")
	elseif stage == STAGE_COORDINATE then
		goal.Text = Text.get("goal.signal_2")
		situation.Text = Text.get("sit.coordinate.drone_waiting")
	elseif stage == STAGE_SLOPE then
		goal.Text = Text.get("goal.signal_3")
		situation.Text = Text.get("sit.slope.bridge_low")
	else
		goal.Text = Text.get("goal.portal")
		situation.Text = Text.get("zone.recommend")
	end
end

local function showHint()
	hintBox.Visible = true
	if stage == STAGE_COORDINATE then
		if hintLevel <= 1 then
			hint.Text = Text.get("hint.coordinate.l1")
		elseif hintLevel == 2 then
			hint.Text = Text.get("hint.coordinate.l2")
		else
			hint.Text = Text.get("hint.coordinate.l3")
		end
	else
		if hintLevel <= 1 then
			hint.Text = Text.get("hint.slope.l1")
		elseif hintLevel == 2 then
			hint.Text = Text.get("hint.slope.l2")
		else
			hint.Text = Text.get("hint.slope.l3")
		end
	end
end

-- 발견한 수학 이름은 2초 크게 보인 뒤 탐험 카드로 줄어든다 (정본 값 cv.label_tag_display)
local function showDiscovery()
	labelBox.Visible = true
	if stage == STAGE_COORDINATE then
		discovery.Text = Text.get("label.coordinate.line")
	else
		discovery.Text = Text.get("label.slope.line")
	end
end

local function clamp(value: number): number
	if value > Layout.GRID_HALF then
		return Layout.GRID_HALF
	end
	if value < -Layout.GRID_HALF then
		return -Layout.GRID_HALF
	end
	return value
end

-- 고른 칸은 월드에서 보여 준다(테두리). 보내는 것은 신호 패널을 켤 때다.
local marker = Instance.new("SelectionBox")
marker.Name = "CellCursor"
marker.Parent = screen

local function showCursor()
	local root = workspace:FindFirstChild("CityLanguageGateWorld")
	local cell = if root then root:FindFirstChild(Layout.cellName(cursorX, cursorY), true) else nil
	marker.Adornee = if cell and cell:IsA("BasePart") then cell else nil
end

local function moveCursor(dx: number, dy: number)
	cursorX, cursorY = clamp(cursorX + dx), clamp(cursorY + dy)
	lastActed = os.clock()
	showCursor()
end

moveRight.Activated:Connect(function()
	moveCursor(1, 0)
end)
moveLeft.Activated:Connect(function()
	moveCursor(-1, 0)
end)
moveUp.Activated:Connect(function()
	moveCursor(0, 1)
end)
moveDown.Activated:Connect(function()
	moveCursor(0, -1)
end)

slopeUp.Activated:Connect(function()
	attempts += 1
	lastActed = os.clock()
	SlopeRemote:FireServer("expr.slope.rise_more")
end)
slopeDown.Activated:Connect(function()
	attempts += 1
	lastActed = os.clock()
	SlopeRemote:FireServer("expr.slope.rise_less")
end)
slopeFlat.Activated:Connect(function()
	attempts += 1
	lastActed = os.clock()
	SlopeRemote:FireServer("expr.slope.flat")
end)

useLabel.Activated:Connect(function()
	showDiscovery()
end)

-- 신호 패널을 켜면 고른 칸을 서버에 보낸다. 신호 1 에서는 켜는 것 자체가 첫 반응이다.
local function onPromptTriggered()
	lastActed = os.clock()
	if stage == STAGE_COORDINATE then
		attempts += 1
		SignalRemote:FireServer(cursorX, cursorY)
	end
end

local function watchPrompt()
	local root = workspace:WaitForChild("CityLanguageGateWorld")
	local panelPart = root:WaitForChild("SignalPanel")
	local prompt = panelPart:WaitForChild("ActivatePrompt")
	if prompt:IsA("ProximityPrompt") then
		prompt.ActionText = Text.get("prompt.signal_panel.activate")
		prompt.Triggered:Connect(onPromptTriggered)
	end
end

ResultRemote.OnClientEvent:Connect(function(code: string)
	hintLevel, lastActed = 0, os.clock()
	if code == "signal_panel_lit" then
		response.Text = Text.get("resp.signal_1.panel_lit")
		stage = STAGE_COORDINATE
		showStage()
		showCursor()
	elseif code == "coordinate_reached" then
		response.Text = Text.get("resp.coordinate.drone_lands")
		showDiscovery()
		stage = STAGE_SLOPE
		showStage()
	elseif code == "coordinate_other" then
		response.Text = Text.get("resp.coordinate.other_spot")
		cursorX, cursorY = 0, 0
		showCursor()
		hintLevel = 1
		showHint()
	elseif code == "slope_reached" then
		response.Text = Text.get("resp.slope.bridge_reaches")
		showDiscovery()
	elseif code == "slope_other" then
		response.Text = Text.get("resp.slope.other_height")
		hintLevel = 1
		showHint()
	elseif code == "gate_opened" then
		response.Text = Text.get("resp.gate_open")
		stage = STAGE_PORTAL
		showStage()
	else
		response.Text = Text.get("retry.again")
	end
end)

-- 진행이 없으면 힌트를 한 단계 올린다 (정본 값 cv.hint_ladder — 무료, 정답은 알려 주지 않는다)
task.spawn(function()
	while true do
		task.wait(1)
		local waiting = stage == STAGE_COORDINATE or stage == STAGE_SLOPE
		if waiting and os.clock() - lastActed >= HINT_IDLE_SECONDS then
			hintLevel += 1
			lastActed = os.clock()
			showHint()
		end
	end
end)

labelBox.Visible = false
showStage()
task.spawn(watchPrompt)
