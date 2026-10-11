--!strict
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local GuiService = game:GetService("GuiService")
local UserInputService = game:GetService("UserInputService")
local Text = require(ReplicatedStorage.Shared.Text)
local WorldView = require(ReplicatedStorage.Shared.WorldView)
local player = Players.LocalPlayer
local input = ReplicatedStorage:WaitForChild("InspectionRemote") :: RemoteEvent
local results = ReplicatedStorage:WaitForChild("ResultRemote") :: RemoteEvent
-- 고정 심사대에서는 가상 이동 버튼이 자료/도장을 덮지 않게 한다.
task.spawn(function()
    local playerModule = require(player:WaitForChild("PlayerScripts"):WaitForChild("PlayerModule"))
    playerModule:GetControls():Disable()
end)

local INK = Color3.fromRGB(238, 242, 246)
local MUTED = Color3.fromRGB(169, 184, 199)
local DARK = Color3.fromRGB(24, 34, 48)
local PANEL = Color3.fromRGB(35, 47, 63)
local TEAL = Color3.fromRGB(107, 214, 194)
local state: any = nil
local busy = false
local sentAt = -10
local requestId = 0
local send: (string, string) -> ()

local gui = Instance.new("ScreenGui")
gui.Name = "InspectionHud"
gui.ResetOnSpawn = false
gui.ScreenInsets = Enum.ScreenInsets.CoreUISafeInsets
gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
gui.Parent = player:WaitForChild("PlayerGui")
local root = Instance.new("Frame")
root.Name = "Content"
root.AnchorPoint = Vector2.new(0.5, 0)
root.Position = UDim2.fromScale(0.5, 0)
root.Size = UDim2.fromScale(1, 1)
root.BackgroundTransparency = 1
root.Parent = gui
local bounds = Instance.new("UISizeConstraint")
bounds.MaxSize = Vector2.new(760, 10000)
bounds.Parent = root

local function round(object: GuiObject)
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, 10)
    corner.Parent = object
end
local function label(parent: Instance, height: number, size: number): TextLabel
    local object = Instance.new("TextLabel")
    object.Size = UDim2.new(1, 0, 0, height)
    object.BackgroundTransparency = 1
    object.Font = Enum.Font.Gotham
    object.TextSize = size
    object.TextColor3 = INK
    object.TextWrapped = true
    object.TextXAlignment = Enum.TextXAlignment.Left
    object.TextYAlignment = Enum.TextYAlignment.Center
    object.Text = Text.get("inspection.empty")
    object.Parent = parent
    return object
end
local function stack(parent: Instance)
    local layout = Instance.new("UIListLayout")
    layout.SortOrder = Enum.SortOrder.LayoutOrder
    layout.Padding = UDim.new(0, 10)
    layout.Parent = parent
end
local function block(parent: Instance): Frame
    local f = Instance.new("Frame")
    f.Size = UDim2.new(1, 0, 0, 0)
    f.AutomaticSize = Enum.AutomaticSize.Y
    f.BackgroundTransparency = 1
    f.Parent = parent
    stack(f)
    return f
end
local function row(parent: Instance): Frame
    local f = Instance.new("Frame")
    f.Size = UDim2.new(1, 0, 0, 50)
    f.BackgroundTransparency = 1
    f.Parent = parent
    local layout = Instance.new("UIListLayout")
    layout.FillDirection = Enum.FillDirection.Horizontal
    layout.Padding = UDim.new(0, 8)
    layout.SortOrder = Enum.SortOrder.LayoutOrder
    layout.Parent = f
    return f
end
local buttons: {TextButton} = {}
local commands: {[TextButton]: {string}} = {}
local function button(parent: Instance, name: string, count: number, action: string, detail: string): TextButton
    local b = Instance.new("TextButton")
    b.Name = name
    b.Size = UDim2.new(1 / count, -(count - 1) * 8 / count, 1, 0)
    b.BackgroundColor3 = PANEL
    b.Font = Enum.Font.GothamMedium
    b.TextSize = 14
    b.TextColor3 = INK
    b.TextWrapped = true
    b.Text = Text.get("inspection.empty")
    b.SelectionOrder = #buttons + 1
    b.Parent = parent
    round(b)
    local pad = Instance.new("UIPadding")
    pad.PaddingLeft = UDim.new(0, 6)
    pad.PaddingRight = UDim.new(0, 6)
    pad.Parent = b
    local outline = Instance.new("UIStroke")
    outline.Name = "Outline"
    outline.ApplyStrokeMode = Enum.ApplyStrokeMode.Border
    outline.Color = TEAL
    outline.Thickness = 2
    outline.Enabled = false
    outline.Parent = b
    b.SelectionGained:Connect(function() outline.Enabled = true end)
    b.SelectionLost:Connect(function() outline.Enabled = state ~= nil and state.selected == detail and action == "evidence" end)
    b.Activated:Connect(function() if b.Active then send(action, detail) end end)
    table.insert(buttons, b)
    commands[b] = {action, detail}
    return b
end

local header = label(root, 40, 18)
header.Position = UDim2.fromOffset(16, 0)
header.Size = UDim2.new(1, -32, 0, 40)
header.Font = Enum.Font.GothamBold
header.Text = Text.get("inspection.title")
local status = label(root, 25, 12)
status.Position = UDim2.fromOffset(16, 40)
status.Size = UDim2.new(1, -32, 0, 25)
status.TextColor3 = MUTED
status.Text = Text.get("inspection.loading")
local scroll = Instance.new("ScrollingFrame")
scroll.Name = "CaseDesk"
scroll.AnchorPoint = Vector2.new(0, 1)
scroll.Position = UDim2.new(0, 12, 1, -12)
scroll.Size = UDim2.new(1, -24, 0.74, -12)
scroll.BackgroundColor3 = DARK
scroll.BackgroundTransparency = 0.06
scroll.BorderSizePixel = 0
scroll.ScrollBarThickness = 4
scroll.ScrollingDirection = Enum.ScrollingDirection.Y
scroll.AutomaticCanvasSize = Enum.AutomaticSize.Y
scroll.CanvasSize = UDim2.new()
scroll.Parent = root
round(scroll)
local pad = Instance.new("UIPadding")
pad.PaddingLeft = UDim.new(0, 14)
pad.PaddingRight = UDim.new(0, 14)
pad.PaddingTop = UDim.new(0, 14)
pad.PaddingBottom = UDim.new(0, 18)
pad.Parent = scroll
stack(scroll)
local intro = block(scroll)
intro.LayoutOrder = 1
local introTitle = label(intro, 30, 22)
introTitle.Text = Text.get("inspection.intro.title")
local introBody = label(intro, 84, 16)
introBody.Text = Text.get("inspection.intro.body")
local startRow = row(intro)
local start = button(startRow, "Start", 1, "start", "none")
start.Text = Text.get("inspection.start")
local claim = label(scroll, 46, 16)
claim.LayoutOrder = 2
claim.Text = Text.get("inspection.claim")
local questionPanel = block(scroll)
questionPanel.LayoutOrder = 3
local questionsTitle = label(questionPanel, 22, 14)
questionsTitle.Text = Text.get("inspection.question.title")
local questions = row(questionPanel)
local qOrigin = button(questions, "AskOrigin", 3, "ask", "origin")
qOrigin.Text = Text.get("inspection.question.origin")
local qMove = button(questions, "AskMove", 3, "ask", "move")
qMove.Text = Text.get("inspection.question.move")
local qRecord = button(questions, "AskRecord", 3, "ask", "record")
qRecord.Text = Text.get("inspection.question.record")

local board = block(scroll)
board.LayoutOrder = 4
local originLine = label(board, 26, 15)
local moveLine = label(board, 26, 15)
local recordLine = label(board, 26, 15)
local axis = label(board, 20, 12)
axis.TextColor3 = MUTED
axis.Text = Text.get("inspection.axes")
local grid = Instance.new("Frame")
grid.Name = "PathComparison"
grid.Size = UDim2.new(1, 0, 0, 164)
grid.BackgroundTransparency = 1
grid.Parent = board
local cells: {[string]: TextLabel} = {}
for y = 0, 3 do
    for x = 0, 3 do
        local cell = label(grid, 36, 13)
        cell.Size = UDim2.new(0.25, -5, 0, 36)
        cell.Position = UDim2.new(x / 4, 0, 0, (3 - y) * 41)
        cell.BackgroundTransparency = 0
        cell.BackgroundColor3 = PANEL
        cell.TextXAlignment = Enum.TextXAlignment.Center
        cell.Text = Text.get("inspection.point", {x = x, y = y})
        round(cell)
        cells[tostring(x) .. ":" .. tostring(y)] = cell
    end
end
local legend = label(board, 40, 12)
legend.TextColor3 = MUTED
legend.Text = Text.get("inspection.legend")
local evidencePanel = block(scroll)
evidencePanel.LayoutOrder = 5
local evidenceTitle = label(evidencePanel, 28, 14)
evidenceTitle.Text = Text.get("inspection.evidence.title")
local evidenceRow = row(evidencePanel)
local eMatch = button(evidenceRow, "EvidenceMatch", 3, "evidence", "match")
eMatch.Text = Text.get("inspection.evidence.match")
local eMismatch = button(evidenceRow, "EvidenceMismatch", 3, "evidence", "mismatch")
eMismatch.Text = Text.get("inspection.evidence.mismatch")
local eMissing = button(evidenceRow, "EvidenceMissing", 3, "evidence", "missing")
eMissing.Text = Text.get("inspection.evidence.missing")
local verdictPanel = block(scroll)
verdictPanel.LayoutOrder = 6
local verdictTitle = label(verdictPanel, 24, 14)
verdictTitle.Text = Text.get("inspection.verdict.title")
local verdictRow = row(verdictPanel)
local approve = button(verdictRow, "Approve", 3, "decide", "approve")
approve.Text = Text.get("inspection.verdict.approve")
local verify = button(verdictRow, "Verify", 3, "decide", "verify")
verify.Text = Text.get("inspection.verdict.verify")
local reject = button(verdictRow, "Reject", 3, "decide", "reject")
reject.Text = Text.get("inspection.verdict.reject")
local feedback = label(scroll, 62, 16)
feedback.LayoutOrder = 7
feedback.TextColor3 = Color3.fromRGB(249, 203, 123)
local resultPanel = block(scroll)
resultPanel.LayoutOrder = 8
local stamp = label(resultPanel, 32, 24)
stamp.Font = Enum.Font.GothamBold
stamp.TextColor3 = TEAL
local reason = label(resultPanel, 64, 16)
local mathName = label(resultPanel, 24, 15)
mathName.Text = Text.get("term.coordinate.name")
local mathMeaning = label(resultPanel, 40, 14)
mathMeaning.TextColor3 = MUTED
mathMeaning.Text = Text.get("inspection.label.meaning")
local choiceRow = row(resultPanel)
local nextCase = button(choiceRow, "NextCase", 2, "next", "none")
nextCase.Text = Text.get("inspection.next")
local rest = button(choiceRow, "Rest", 2, "rest", "none")
rest.Text = Text.get("pacing.rest")
local restPanel = block(scroll)
restPanel.LayoutOrder = 9
local restBody = label(restPanel, 80, 18)
restBody.Text = Text.get("inspection.rest.body")
local resumeRow = row(restPanel)
local resume = button(resumeRow, "Resume", 1, "resume", "none")
resume.Text = Text.get("inspection.resume")

local function focus(b: TextButton)
    GuiService.SelectedObject = b
end
local function enabled(b: TextButton, allowed: boolean)
    b.Active = allowed and not busy
    b.Selectable = b.Active
    b.AutoButtonColor = b.Active
    b.TextTransparency = if b.Active then 0 else 0.55
end
local function render()
    local phase = if state then state.phase else "ready"
    intro.Visible = phase == "ready"
    claim.Visible = phase == "review" or phase == "resolved"
    questionPanel.Visible = phase == "review"
    board.Visible = phase == "review" or phase == "resolved"
    resultPanel.LayoutOrder = if phase == "resolved" then 3 else 8
    evidencePanel.Visible = phase == "review"
    verdictPanel.Visible = phase == "review"
    resultPanel.Visible = phase == "resolved"
    restPanel.Visible = phase == "rest"
    feedback.Visible = phase == "review" and state ~= nil and state.feedback ~= nil
    enabled(start, state ~= nil and phase == "ready")
    enabled(resume, phase == "rest")
    enabled(nextCase, phase == "resolved")
    enabled(rest, phase == "resolved")
    for _, b in {qOrigin, qMove, qRecord} do enabled(b, phase == "review") end
    local allAsked = state ~= nil and state.asked.origin and state.asked.move and state.asked.record
    for _, b in {eMatch, eMismatch, eMissing} do
        enabled(b, phase == "review" and allAsked == true)
        local outline = b:FindFirstChild("Outline") :: UIStroke
        outline.Enabled = GuiService.SelectedObject == b or (state ~= nil and state.selected == commands[b][2])
    end
    for _, b in {approve, verify, reject} do enabled(b, phase == "review" and state ~= nil and state.selected ~= nil) end
    if not state then return end
    if state.asked.origin then qOrigin.Text = Text.get("inspection.question.origin.done")
    else qOrigin.Text = Text.get("inspection.question.origin") end
    if state.asked.move then qMove.Text = Text.get("inspection.question.move.done")
    else qMove.Text = Text.get("inspection.question.move") end
    if state.asked.record then qRecord.Text = Text.get("inspection.question.record.done")
    else qRecord.Text = Text.get("inspection.question.record") end
    if busy then status.Text = Text.get("inspection.sending")
    else status.Text = Text.get("inspection.progress", {count = state.completed}) end
    if not state.asked.origin then originLine.Text = Text.get("inspection.origin.hidden")
    elseif state.origin then originLine.Text = Text.get("inspection.origin.point", {x = state.origin.x, y = state.origin.y})
    else originLine.Text = Text.get("inspection.origin.missing") end
    if state.move then moveLine.Text = Text.get("inspection.move.point", {x = state.move.x, y = state.move.y})
    else moveLine.Text = Text.get("inspection.move.hidden") end
    if not state.asked.record then recordLine.Text = Text.get("inspection.record.hidden")
    elseif state.record then recordLine.Text = Text.get("inspection.record.point", {x = state.record.x, y = state.record.y})
    else recordLine.Text = Text.get("inspection.record.missing") end
    for y = 0, 3 do
        for x = 0, 3 do
            local cell = cells[tostring(x) .. ":" .. tostring(y)]
            cell.BackgroundColor3 = PANEL
            cell.TextColor3 = INK
            cell.Text = Text.get("inspection.point", {x = x, y = y})
        end
    end
    local origin = state.origin
    local move = state.move
    if origin and move then
        for x = origin.x, origin.x + move.x do
            local cell = cells[tostring(x) .. ":" .. tostring(origin.y)]
            if cell then cell.BackgroundColor3 = Color3.fromRGB(56, 98, 111) end
        end
        for y = origin.y, origin.y + move.y do
            local cell = cells[tostring(origin.x + move.x) .. ":" .. tostring(y)]
            if cell then cell.BackgroundColor3 = Color3.fromRGB(56, 98, 111) end
        end
        local destination = cells[tostring(origin.x + move.x) .. ":" .. tostring(origin.y + move.y)]
        if destination then destination.Text = Text.get("inspection.path.point", {x = origin.x + move.x, y = origin.y + move.y}) end
    end
    if state.record then
        local cell = cells[tostring(state.record.x) .. ":" .. tostring(state.record.y)]
        if cell then
            if origin and move and origin.x + move.x == state.record.x and origin.y + move.y == state.record.y then
                cell.Text = Text.get("inspection.match.cell", {x = state.record.x, y = state.record.y})
            else cell.Text = Text.get("inspection.record.cell", {x = state.record.x, y = state.record.y}) end
            cell.BackgroundColor3 = Color3.fromRGB(120, 90, 44)
        end
    end
    if state.feedback == "need_questions" then feedback.Text = Text.get("inspection.retry.questions")
    elseif state.feedback == "need_evidence" then feedback.Text = Text.get("inspection.retry.evidence")
    elseif state.feedback == "check_origin" then feedback.Text = Text.get("inspection.retry.origin")
    elseif state.feedback == "check_record" then feedback.Text = Text.get("inspection.retry.record")
    elseif state.feedback == "check_missing" then feedback.Text = Text.get("inspection.retry.missing") end
    if state.verdict == "approve" then
        stamp.Text = Text.get("inspection.result.approve")
        reason.Text = Text.get("inspection.result.match")
    elseif state.verdict == "verify" then
        stamp.Text = Text.get("inspection.result.verify")
        reason.Text = Text.get("inspection.result.missing")
    elseif state.verdict == "reject" then
        stamp.Text = Text.get("inspection.result.reject")
        reason.Text = Text.get("inspection.result.mismatch")
    end
end
local function replayPath()
    if not state or not state.origin or not state.move or state.phase ~= "review" then return end
    local turn = state.token
    local revision = requestId
    local path = {}
    for x = state.origin.x, state.origin.x + state.move.x do
        table.insert(path, {x = x, y = state.origin.y})
    end
    for y = state.origin.y + 1, state.origin.y + state.move.y do
        table.insert(path, {x = state.origin.x + state.move.x, y = y})
    end
    for _, point in path do
        local cell = cells[tostring(point.x) .. ":" .. tostring(point.y)]
        if cell then cell.BackgroundColor3 = PANEL end
    end
    for i, point in path do
        task.delay((i - 1) * 0.12, function()
            if not state or state.token ~= turn or requestId ~= revision then return end
            local cell = cells[tostring(point.x) .. ":" .. tostring(point.y)]
            if cell then
                cell.BackgroundColor3 = if state.record and state.record.x == point.x and state.record.y == point.y
                    then Color3.fromRGB(120, 90, 44) else Color3.fromRGB(56, 98, 111)
            end
        end)
    end
end
send = function(action: string, detail: string)
    if busy or not state or os.clock() - sentAt < 0.55 then return end
    busy = true
    sentAt = os.clock()
    requestId += 1
    local thisRequest = requestId
    input:FireServer(action, detail, state.token)
    render()
    task.delay(2, function()
        if busy and requestId == thisRequest then
            busy = false
            render()
            input:FireServer("sync", "none", state.token)
        end
    end)
end
results.OnClientEvent:Connect(function(snapshot: any, event: string?)
    if typeof(snapshot) ~= "table" then return end
    local oldPhase = if state then state.phase else nil
    local oldToken = if state then state.token else nil
    state = snapshot
    busy = false
    render()
    WorldView.show(state.token, state.phase, state.verdict)
    if event == "question_opened" or event == "replayed" then replayPath() end
    if oldPhase ~= state.phase or oldToken ~= state.token then
        scroll.CanvasPosition = Vector2.zero
        if UserInputService.GamepadEnabled then
            if state.phase == "review" then focus(qOrigin)
            elseif state.phase == "resolved" then focus(nextCase)
            elseif state.phase == "rest" then focus(resume)
            else focus(start) end
        end
    elseif UserInputService.GamepadEnabled and event == "evidence_selected" then focus(approve) end
end)
GuiService.GuiNavigationEnabled = true
GuiService:GetPropertyChangedSignal("SelectedObject"):Connect(function()
    local b = GuiService.SelectedObject
    if b and b:IsDescendantOf(scroll) then
        local top = b.AbsolutePosition.Y - scroll.AbsolutePosition.Y + scroll.CanvasPosition.Y
        if top < scroll.CanvasPosition.Y or top + b.AbsoluteSize.Y > scroll.CanvasPosition.Y + scroll.AbsoluteSize.Y then
            scroll.CanvasPosition = Vector2.new(0, math.max(0, top - 30))
        end
    end
end)
UserInputService.InputBegan:Connect(function(key: InputObject, consumed: boolean)
    if consumed or not state then return end
    local shortcuts = {
        [Enum.KeyCode.Q] = qOrigin, [Enum.KeyCode.W] = qMove, [Enum.KeyCode.E] = qRecord,
        [Enum.KeyCode.One] = eMatch, [Enum.KeyCode.Two] = eMismatch, [Enum.KeyCode.Three] = eMissing,
        [Enum.KeyCode.A] = approve, [Enum.KeyCode.S] = verify, [Enum.KeyCode.D] = reject,
        [Enum.KeyCode.N] = nextCase, [Enum.KeyCode.Space] = if state.phase == "rest" then resume else rest,
        [Enum.KeyCode.Return] = start,
    }
    local b = shortcuts[key.KeyCode]
    if b and b.Active and b.Parent and b.Parent:IsA("GuiObject") and b.Parent.Visible then
        local command = commands[b]
        send(command[1], command[2])
    end
end)
local function hideCharacter(character: Model)
    for _, p in character:GetDescendants() do
        if p:IsA("BasePart") then p.LocalTransparencyModifier = 1 end
    end
end
player.CharacterAdded:Connect(hideCharacter)
if player.Character then hideCharacter(player.Character) end
local camera = workspace.CurrentCamera
if camera then
    camera.CameraType = Enum.CameraType.Scriptable
    camera.CFrame = CFrame.lookAt(Vector3.new(0, 7, 12), Vector3.new(0, 0, -2.8))
    camera.FieldOfView = 40
end
render()
task.spawn(function()
    while not state and gui.Parent do
        input:FireServer("sync", "none", "0")
        task.wait(0.7)
    end
    if UserInputService.GamepadEnabled then focus(start) end
end)
