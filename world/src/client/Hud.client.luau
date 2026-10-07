--!strict
-- 화면은 현재 목표 하나만 보여 준다 (K5). 판정은 서버가 하고 클라이언트는 고른 것만 보낸다 (INV-4).
-- 글자는 모두 번역표를 거친다 — 코드에는 키만 쓴다 (INV-3). 색만으로 뜻을 전하지 않는다 (INV-9).
-- 배치 (S9): 목표 카드는 오른쪽 위 — 왼쪽 위 채팅창과 출발 칸을 가리지 않는다. 고르는 패널은 아래 띠의
-- 터치 조이스틱(왼쪽)과 점프 버튼(오른쪽) 사이. 탐험 카드는 위 메뉴 줄의 빈자리. 화면이 바뀌면 다시 놓는다.
local GuiService = game:GetService("GuiService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local UserInputService = game:GetService("UserInputService")

local Text = require(ReplicatedStorage.Shared.Text)
local Layout = require(ReplicatedStorage.Shared.Layout)

local SignalRemote = ReplicatedStorage:WaitForChild("SignalRemote")
local SlopeRemote = ReplicatedStorage:WaitForChild("SlopeRemote")
local ResultRemote = ReplicatedStorage:WaitForChild("ResultRemote")

local STAGE_PANEL, STAGE_COORDINATE, STAGE_SLOPE, STAGE_PORTAL, STAGE_DONE = "panel", "coordinate", "slope", "portal", "done"
local HINT_IDLE_SECONDS = 10   -- 정본 값 cv.hint_ladder.first_trigger.idle_seconds
local LABEL_FULL_SECONDS = 2   -- 정본 값 cv.label_tag_display.full_seconds — 크게 보인 뒤 탐험 카드로 줄어든다
local RESPONSE_FRESH_SECONDS = 4   -- 방금 온 응답은 이 동안 상황 설명보다 앞에 둔다 (작은 화면에서 한쪽만 들어갈 때)
local COMPACT_HEIGHT = 420     -- 이보다 낮은 화면(가로로 든 휴대폰)은 줄·버튼·글자를 줄인다
local MIN_TEXT = 10            -- 글자를 칸에 맞춰 줄여도 이보다 작게는 하지 않는다
local TV_SAFE = 0.05           -- TV 는 가장자리가 잘릴 수 있다 — 짧은 변의 5% 안쪽에만 둔다
local STICK_SHARE = 0.4        -- 터치 조이스틱 자리를 못 찾으면 왼쪽 40% 로 어림한다 (기본 PlayerModule 실측과 같음)
local JUMP_ROOM = 110          -- 점프 버튼 자리를 못 찾으면 오른쪽 끝에서 이만큼 비운다

local stage = STAGE_PANEL
local cursorX, cursorY = 0, 0
local hintLevel, attempts, lastActed = 0, 0, os.clock()
local respondedAt = -math.huge

local playerGui = Players.LocalPlayer:WaitForChild("PlayerGui")   -- 화면에 그려지는 곳은 PlayerGui 뿐이다

-- 기본 여백(CoreUISafeInsets)이 위 메뉴 줄과 화면 양옆 안전 영역을 이미 뺀다 (S9 실측)
local screen = Instance.new("ScreenGui")
screen.Name = "GateHud"
screen.ResetOnSpawn = false
screen.Parent = playerGui

-- 탐험 카드 자리: 위 메뉴 줄에서 Roblox 단추가 쓰지 않는 칸. 그 칸이 없는 기기에서는 목표 카드 아래로 간다
local cardScreen = Instance.new("ScreenGui")
cardScreen.Name = "GateCard"
cardScreen.ResetOnSpawn = false
cardScreen.ScreenInsets = Enum.ScreenInsets.TopbarSafeInsets
cardScreen.Parent = playerGui

local function panel(name: string, parent: Instance): Frame
	local frame = Instance.new("Frame")
	frame.Name = name
	frame.BackgroundTransparency = 0.3
	frame.Parent = parent
	return frame
end

-- 글자는 칸에 맞춰 줄인다(TextScaled). 크기 상한·하한은 layout 이 화면 크기로 정한다
local function fit(item: GuiObject)
	local limit = Instance.new("UITextSizeConstraint")
	limit.Parent = item
end

local function label(name: string, parent: Instance): TextLabel
	local item = Instance.new("TextLabel")
	item.Name = name
	item.TextScaled = true
	item.TextWrapped = true
	item.BackgroundTransparency = 1
	item.Parent = parent
	fit(item)
	return item
end

local function button(name: string, parent: Instance): TextButton
	local item = Instance.new("TextButton")
	item.Name = name
	item.TextScaled = true
	item.TextWrapped = true
	item.Parent = parent
	fit(item)
	return item
end

-- 목표 카드: 목표 · 상황 · 응답 · 힌트 줄
local top = panel("Top", screen)
local goal = label("Goal", top)
local situation = label("Situation", top)
local response = label("Response", top)
local hint = label("HintText", top)
for _, row in {situation, response, hint} do
	row.TextXAlignment = Enum.TextXAlignment.Left
	row.Visible = false   -- 첫 배치 전에는 TextLabel 기본 글자("Label")가 보이지 않게 숨긴다
end
-- 줄마다 보일 내용이 있는지. 실제로 보이는지는 layout 이 남는 높이로 정한다
local wanted: {[TextLabel]: boolean} = {[goal] = true, [situation] = true, [response] = false, [hint] = false}

-- 이름표: 수학 이름을 2초 크게 보인 뒤 탐험 카드의 이름 하나로 줄어든다 (정본 값 cv.label_tag_display)
local labelBox = panel("Discovery", screen)
labelBox.ZIndex = 3   -- 크게 보이는 2초 동안은 다른 패널 위에
labelBox.Visible = false
local discoveryName = label("DiscoveryName", labelBox)
local discovery = label("DiscoveryText", labelBox)

-- 탐험 카드: 발견한 수학 이름이 모인다
local card = Instance.new("Frame")
card.Name = "ExplorationCard"
card.BackgroundTransparency = 1
card.Parent = cardScreen
local cardList = Instance.new("UIListLayout")
cardList.FillDirection = Enum.FillDirection.Horizontal
cardList.HorizontalAlignment = Enum.HorizontalAlignment.Right
cardList.VerticalAlignment = Enum.VerticalAlignment.Center
cardList.SortOrder = Enum.SortOrder.LayoutOrder
cardList.Parent = card
local coordinateTerm = label("TermCoordinate", card)
local slopeTerm = label("TermSlope", card)
coordinateTerm.LayoutOrder, slopeTerm.LayoutOrder = 1, 2
for _, term in {coordinateTerm, slopeTerm} do
	term.BackgroundTransparency = 0.3
	term.Visible = false
end

local moves = panel("Moves", screen)
local moveRight = button("MoveRight", moves)
local moveLeft = button("MoveLeft", moves)
local moveUp = button("MoveUp", moves)
local moveDown = button("MoveDown", moves)

local slopes = panel("Slopes", screen)
local slopeUp = button("SlopeUp", slopes)
local slopeDown = button("SlopeDown", slopes)
local slopeFlat = button("SlopeFlat", slopes)

-- 멈춤 지점: 두 선택지는 같은 크기·같은 모습이고 어느 쪽도 미리 고르지 않는다 (pacing.stop_point.equal_size)
local stopPoint = panel("StopPoint", screen)
local keepGoing = button("Continue", stopPoint)
local takeRest = button("Rest", stopPoint)

-- 버튼 글자는 한 번만 넣는다 — 키는 글자 그대로 적어 검사할 수 있게 한다
moveRight.Text = Text.get("action.position.move_right")
moveLeft.Text = Text.get("action.position.move_left")
moveUp.Text = Text.get("action.position.move_up")
moveDown.Text = Text.get("action.position.move_down")
slopeUp.Text = Text.get("action.slope.increase")
slopeDown.Text = Text.get("action.slope.decrease")
slopeFlat.Text = Text.get("action.slope.set_zero")
keepGoing.Text = Text.get("pacing.continue")
takeRest.Text = Text.get("pacing.rest")
coordinateTerm.Text = Text.get("term.coordinate.name")
slopeTerm.Text = Text.get("term.slope.name")

-- 입력 3종 (K4 U6·U9 · INV-9). 터치·마우스는 버튼을 바로 누르고, 패널·입구는 근접 프롬프트(E·ButtonX·탭)로 켠다.
-- 게임패드 초점은 지금 고르는 패널의 틀에 먼저 둔다 — 어느 선택지도 미리 고르지 않는다 (멈춤 지점 두 선택지는 같게, K6 R7).
local choicePanels = {moves, slopes, stopPoint}
for _, group in choicePanels do
	group.Selectable = true
	group.SelectionOrder = -1   -- Select 버튼·\ 로 선택을 켜면 버튼(기본 0)보다 틀이 먼저 잡힌다
	group.Visible = false
end

-- 이동 순서 (U9): 칸마다 네 방향을 모두 적는다(자기 자신 = 그대로) — 비운 방향을 엔진이 알아서 골라 패널 밖으로 새지 않게
local function link(item: GuiObject, up: GuiObject, down: GuiObject, left: GuiObject, right: GuiObject)
	item.NextSelectionUp = up
	item.NextSelectionDown = down
	item.NextSelectionLeft = left
	item.NextSelectionRight = right
end
-- 십자: 어디서든 누른 방향의 버튼으로 간다 — 패드 방향 = 화면 방향 = 루미가 갈 방향
for _, item in ({moves, moveUp, moveLeft, moveRight, moveDown} :: {GuiObject}) do
	link(item, moveUp, moveDown, moveLeft, moveRight)
end
-- 기울기 세로 한 줄: 틀에서는 가장 가까운 칸으로 들어간다(위 = 가운데, 아래 = 맨 아래) — 한 번 눌러 맨 위에 닿지 않는다
link(slopes, slopeDown, slopeFlat, slopes, slopes)
link(slopeUp, slopeUp, slopeDown, slopeUp, slopeUp)
link(slopeDown, slopeUp, slopeFlat, slopeDown, slopeDown)
link(slopeFlat, slopeDown, slopeFlat, slopeFlat, slopeFlat)
-- 멈춤 지점: 어디서든 왼쪽 = 계속하기, 오른쪽 = 쉬기 — 두 쪽 모두 한 번 눌러 닿는다
for _, item in ({stopPoint, keepGoing, takeRest} :: {GuiObject}) do
	link(item, item, item, keepGoing, takeRest)
end

-- 게임패드일 때만, 지금 보이는 고르는 패널(단계마다 하나뿐)의 틀에 초점을 둔다. 걷는 단계·다른 입력 장치에서는
-- 초점을 직접 풀어 이동을 돌려준다 — 패널을 숨기거나 Selectable 을 꺼서는 풀리지 않는다.
local function focusPanel()
	local focusTarget: GuiObject? = nil
	if UserInputService.PreferredInput == Enum.PreferredInput.Gamepad then
		for _, group in choicePanels do
			if group.Visible then
				focusTarget = group
			end
		end
	end
	GuiService.SelectedObject = focusTarget
end

local function place(item: GuiObject, x: number, y: number, width: number, height: number)
	item.Position = UDim2.fromOffset(math.floor(x), math.floor(y))
	item.Size = UDim2.fromOffset(math.floor(width), math.floor(height))
end

local function textLimit(item: GuiObject, size: number)
	local limit = item:FindFirstChildOfClass("UITextSizeConstraint")
	if limit then
		limit.MaxTextSize = size
		limit.MinTextSize = math.min(size, MIN_TEXT)
	end
end

-- 아래 띠에서 터치 조작(기본 PlayerModule 의 TouchGui)이 차지하지 않는 가로 구간. 못 찾으면 비율로 어림한다
local function band(width: number): (number, number)
	if UserInputService.PreferredInput ~= Enum.PreferredInput.Touch then
		return 0, width
	end
	local origin = screen.AbsolutePosition.X
	local controls = playerGui:FindFirstChild("TouchGui")
	local frame = if controls then controls:FindFirstChild("TouchControlFrame") else nil
	local stick = if frame then frame:FindFirstChild("DynamicThumbstickFrame") or frame:FindFirstChild("ThumbstickFrame") else nil
	local jump = if frame then frame:FindFirstChild("JumpButton") else nil
	local left, right = width * STICK_SHARE, width - JUMP_ROOM
	if stick and stick:IsA("GuiObject") and stick.Visible then
		left = stick.AbsolutePosition.X + stick.AbsoluteSize.X - origin
	end
	if jump and jump:IsA("GuiObject") and jump.Visible then
		right = jump.AbsolutePosition.X - origin
	end
	return left, right
end

-- 화면 크기에 맞춰 모든 패널을 놓는다. 화면을 돌리거나 단계·줄이 바뀔 때마다 다시 부른다
local function layout()
	local area = screen.AbsoluteSize
	if area.X < 1 or area.Y < 1 then
		return
	end
	local compact = area.Y < COMPACT_HEIGHT
	local tv = GuiService:IsTenFootInterface()
	local margin = if tv then math.floor(math.max(area.X, area.Y) * TV_SAFE) elseif compact then 8 else 16
	local gap = if compact then 4 else 8
	local line = if compact then 17 else 26        -- 글자 한 줄 높이
	local rowHeight = if compact then 44 else 52   -- 손가락으로 누르는 버튼 높이 (44 이상)
	local textSize = if compact then 14 else 20

	-- 고르는 패널: 아래 띠 가운데, 터치 조작 사이
	local left, right = band(area.X)
	left, right = math.max(left + gap, margin), math.min(right - gap, area.X - margin)
	local width = math.max(right - left, 0)
	local bottom = area.Y - margin
	local cell = math.min(math.floor((width - 2 * gap) / 3), if compact then 120 else 170)
	local crossWidth, crossHeight = 3 * cell + 2 * gap, 3 * rowHeight + 2 * gap
	place(moves, left + (width - crossWidth) / 2, bottom - crossHeight, crossWidth, crossHeight)
	place(moveUp, cell + gap, 0, cell, rowHeight)
	place(moveLeft, 0, rowHeight + gap, cell, rowHeight)
	place(moveRight, 2 * (cell + gap), rowHeight + gap, cell, rowHeight)
	place(moveDown, cell + gap, 2 * (rowHeight + gap), cell, rowHeight)
	local slopeWidth = math.min(width, if compact then 200 else 280)
	local slopeHeight = 3 * rowHeight + 2 * gap
	place(slopes, left + (width - slopeWidth) / 2, bottom - slopeHeight, slopeWidth, slopeHeight)
	for k, item in {slopeUp, slopeDown, slopeFlat} do
		place(item, 0, (k - 1) * (rowHeight + gap), slopeWidth, rowHeight)
	end
	local choiceWidth = math.min(math.floor((width - gap) / 2), if compact then 150 else 200)
	local stopWidth = 2 * choiceWidth + gap
	place(stopPoint, left + (width - stopWidth) / 2, bottom - rowHeight, stopWidth, rowHeight)
	place(keepGoing, 0, 0, choiceWidth, rowHeight)
	place(takeRest, choiceWidth + gap, 0, choiceWidth, rowHeight)
	for _, item in {moveUp, moveLeft, moveRight, moveDown, slopeUp, slopeDown, slopeFlat, keepGoing, takeRest} do
		textLimit(item, textSize)
	end

	-- 목표 카드: 오른쪽 위. 고르는 패널 위로 남는 높이에 들어가는 줄만 둔다 — 목표 > 힌트 > 상황 > 응답,
	-- 방금 온 응답은 RESPONSE_FRESH_SECONDS 동안 목표 다음으로 앞선다
	local floor = bottom
	for _, group in choicePanels do
		if group.Visible then
			floor = math.min(floor, group.Position.Y.Offset)
		end
	end
	local cardWidth = math.clamp(math.floor(area.X * (if compact then 0.46 else 0.32)), 240, 480)
	local heights = {[goal] = line + 6, [situation] = 3 * line, [response] = 2 * line, [hint] = 3 * line}
	local fresh = os.clock() - respondedAt < RESPONSE_FRESH_SECONDS
	local order = if fresh then {goal, response, hint, situation} else {goal, hint, situation, response}
	local room = floor - gap - margin - 2 * gap
	local shown: {[TextLabel]: boolean} = {}
	for _, row in order do
		if wanted[row] and heights[row] <= room then
			shown[row] = true
			room -= heights[row] + gap
		end
	end
	local y = gap
	for _, row in {goal, situation, response, hint} do
		row.Visible = shown[row] == true
		if row.Visible then
			place(row, gap, y, cardWidth - 2 * gap, heights[row])
			textLimit(row, if row == goal then textSize + 2 else textSize)
			y += heights[row] + gap
		end
	end
	top.Visible = y > gap
	place(top, area.X - margin - cardWidth, margin, cardWidth, y)

	-- 이름표 2초: 화면 가운데 크게
	local labelWidth = math.min(area.X - 2 * margin, if compact then 520 else 640)
	local nameHeight = 2 * line + 8
	local labelHeight = nameHeight + 3 * line + 3 * gap
	place(labelBox, (area.X - labelWidth) / 2, math.max(margin, (area.Y - labelHeight) / 2), labelWidth, labelHeight)
	place(discoveryName, gap, gap, labelWidth - 2 * gap, nameHeight)
	place(discovery, gap, 2 * gap + nameHeight, labelWidth - 2 * gap, 3 * line)
	textLimit(discoveryName, 2 * textSize + 8)
	textLimit(discovery, textSize)

	-- 탐험 카드: 위 메뉴 줄의 빈칸 오른쪽 끝. 그 칸이 없거나 낮으면, 또 TV 에서는(맨 위가 잘릴 수 있다) 목표 카드 바로 아래
	local bar = cardScreen.AbsoluteSize
	local onBar = not tv and bar.Y >= 24 and bar.X >= 160
	local chipHeight = if onBar then math.min(bar.Y - 16, 32) else line + 8
	if onBar then
		card.Parent = cardScreen
		place(card, 0, 0, bar.X - margin, bar.Y)
	else
		card.Parent = screen
		place(card, area.X - margin - cardWidth, margin + y + gap, cardWidth, chipHeight)
	end
	cardList.Padding = UDim.new(0, gap)
	for _, term in {coordinateTerm, slopeTerm} do
		term.Size = UDim2.fromOffset(3 * chipHeight, chipHeight)
		textLimit(term, textSize)
	end
end

local function showStage()
	moves.Visible = stage == STAGE_COORDINATE
	slopes.Visible = stage == STAGE_SLOPE
	stopPoint.Visible = stage == STAGE_DONE
	wanted[goal] = stage ~= STAGE_DONE   -- 입구에 들어가면 남은 목표가 없다. 추천 구역 안내는 다음 목표로 남긴다
	wanted[hint] = false
	if stage == STAGE_DONE then
		labelBox.Visible = false   -- 끝 화면에는 멈춤 지점 선택지 둘만 둔다
	end
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
	layout()
	focusPanel()
end

local function showHint()
	wanted[hint] = true
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
	layout()
end

-- 발견한 수학 이름은 2초 크게 보인 뒤 탐험 카드로 줄어든다 (정본 값 cv.label_tag_display — 진행을 막지 않는다)
local discoveries = 0   -- 이름표가 겹치면 마지막 것만 2초 뒤에 닫는다
local function showDiscovery()
	discoveries += 1
	local mine = discoveries
	local term = coordinateTerm
	if stage == STAGE_COORDINATE then
		discoveryName.Text = Text.get("term.coordinate.name")
		discovery.Text = Text.get("label.coordinate.line")
	else
		term = slopeTerm
		discoveryName.Text = Text.get("term.slope.name")
		discovery.Text = Text.get("label.slope.line")
	end
	labelBox.Visible = true
	task.delay(LABEL_FULL_SECONDS, function()
		term.Visible = true   -- 탐험 카드에 이름이 남는다
		if mine == discoveries then
			labelBox.Visible = false
		end
	end)
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
marker.Color3 = Color3.fromRGB(0, 0, 0)   -- 어느 칸 색(꺼짐·깜박임·켜짐·출발) 위에서도 3:1 이상 — 기본 파랑은 꺼진 칸 위에서 거의 사라진다
marker.LineThickness = 0.2
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

-- 어느 쪽을 골라도 선택 창만 닫힌다 — 다음 미션은 저절로 시작하지 않는다(pacing.autoplay_next_mission).
-- 광장 미션(m.plaza_*)이 생기면 '계속하기'가 그쪽으로 이어진다.
local function closeStopPoint()
	stopPoint.Visible = false
	layout()
	focusPanel()   -- 고르고 나면 초점을 풀어 다시 걷게 한다
end
keepGoing.Activated:Connect(closeStopPoint)
takeRest.Activated:Connect(closeStopPoint)

-- 신호 패널을 켜면 고른 칸을 서버에 보낸다. 신호 1 에서는 켜는 것 자체가 첫 반응이다.
local function onPromptTriggered()
	lastActed = os.clock()
	if stage == STAGE_COORDINATE then
		attempts += 1
		SignalRemote:FireServer(cursorX, cursorY)
	end
end

local portalPrompt: ProximityPrompt? = nil

local function watchPrompt()
	local root = workspace:WaitForChild("CityLanguageGateWorld")
	local panelPart = root:WaitForChild("SignalPanel")
	local prompt = panelPart:WaitForChild("ActivatePrompt")
	if prompt:IsA("ProximityPrompt") then
		prompt.ActionText = Text.get("prompt.signal_panel.activate")
		prompt.Triggered:Connect(onPromptTriggered)
	end
	local found = root:WaitForChild("ZonePortal"):WaitForChild("EnterPrompt")
	if found:IsA("ProximityPrompt") then
		found.ActionText = Text.get("zone.metro_district.name")
		portalPrompt = found
	end
end

ResultRemote.OnClientEvent:Connect(function(code: string)
	hintLevel, lastActed = 0, os.clock()
	respondedAt = os.clock()
	wanted[response] = true
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
		focusPanel()   -- 커서가 출발 칸으로 돌아오면 초점도 틀로 돌아온다
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
	elseif code == "zone_portal_entered" then
		wanted[response] = false   -- 입구에 들어간 반응은 멈춤 지점 선택지가 맡는다
		if portalPrompt then
			portalPrompt.Enabled = false   -- 이미 쓴 입구 — 이 플레이어 화면에서만 끈다(서버·다른 플레이어는 그대로)
		end
		stage = STAGE_DONE
		showStage()
	else
		response.Text = Text.get("retry.again")
	end
	layout()
	task.delay(RESPONSE_FRESH_SECONDS, layout)   -- 응답이 묵으면 작은 화면에서는 상황 설명이 다시 앞선다
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
			-- 기울기 단계에서 초점을 잃고(Select·B·메뉴) 서 있는 게임패드 플레이어에게 패널을 다시 건넨다. 걷는 중에는 빼앗지 않는다.
			-- 좌표 단계는 패널 앞 X(보내기 → 다른 칸 → 초점 복귀)가 같은 길이다 — 패널에서 먼 곳에서 초점에 묶이지 않게 넣지 않는다
			local character = Players.LocalPlayer.Character
			local humanoid = if character then character:FindFirstChildOfClass("Humanoid") else nil
			local standing = humanoid ~= nil and humanoid:IsA("Humanoid") and humanoid.MoveDirection.Magnitude == 0
			if stage == STAGE_SLOPE and standing and GuiService.SelectedObject == nil then
				focusPanel()
			end
		end
	end
end)

showStage()
task.spawn(watchPrompt)
UserInputService:GetPropertyChangedSignal("PreferredInput"):Connect(function()
	layout()       -- 터치로 바뀌면 조이스틱·점프 버튼 자리를 비운다
	focusPanel()   -- 패드를 잡거나 놓으면 초점을 다시 정한다
end)
screen:GetPropertyChangedSignal("AbsoluteSize"):Connect(layout)   -- 화면을 돌리거나 창 크기를 바꾸면 다시 놓는다
cardScreen:GetPropertyChangedSignal("AbsoluteSize"):Connect(layout)
playerGui.ChildAdded:Connect(function(child: Instance)
	if child.Name == "TouchGui" then
		task.delay(0.5, layout)   -- 터치 조작은 PlayerModule 이 따로 만든다 — 자리가 잡힌 뒤 다시 놓는다
	end
end)
task.delay(1, layout)
