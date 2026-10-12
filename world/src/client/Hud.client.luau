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
local PATH = Color3.fromRGB(56, 98, 111)
local RECORD = Color3.fromRGB(120, 90, 44)
local LINE = Color3.fromRGB(150, 128, 52)
local state: any = nil
local busy = false
local sentAt = -10
local requestId = 0
local wide = false
local send: (string, string) -> ()

local gui = Instance.new("ScreenGui")
gui.Name = "InspectionHud"
gui.ResetOnSpawn = false
gui.ScreenInsets = Enum.ScreenInsets.CoreUISafeInsets
gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
gui.Parent = player:WaitForChild("PlayerGui")
local root = Instance.new("Frame")
root.Name = "Content"
root.Size = UDim2.fromScale(1, 1)
root.BackgroundTransparency = 1
root.Parent = gui

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
    layout.Padding = UDim.new(0, 8)
    layout.Parent = parent
end
local function block(parent: Instance, order: number): Frame
    local f = Instance.new("Frame")
    f.Size = UDim2.new(1, 0, 0, 0)
    f.AutomaticSize = Enum.AutomaticSize.Y
    f.BackgroundTransparency = 1
    f.LayoutOrder = order
    f.Parent = parent
    stack(f)
    return f
end
local function row(parent: Instance, height: number): Frame
    local f = Instance.new("Frame")
    f.Size = UDim2.new(1, 0, 0, height)
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
    b.TextSize = 13
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
header.Font = Enum.Font.GothamBold
header.Text = Text.get("inspection.title")
local status = label(root, 25, 13)
status.TextColor3 = INK
status.TextStrokeTransparency = 0.4
status.Text = Text.get("inspection.loading")
local scroll = Instance.new("ScrollingFrame")
scroll.Name = "CaseDesk"
scroll.BackgroundColor3 = DARK
scroll.BackgroundTransparency = 0.06
scroll.BorderSizePixel = 0
scroll.ScrollBarThickness = 4
scroll.ScrollingDirection = Enum.ScrollingDirection.Y
scroll.AutomaticCanvasSize = Enum.AutomaticSize.Y
scroll.CanvasSize = UDim2.new()
scroll.Parent = root
round(scroll)
local bounds = Instance.new("UISizeConstraint")
bounds.MaxSize = Vector2.new(760, 10000)
bounds.Parent = scroll
local pad = Instance.new("UIPadding")
pad.PaddingLeft = UDim.new(0, 12)
pad.PaddingRight = UDim.new(0, 12)
pad.PaddingTop = UDim.new(0, 12)
pad.PaddingBottom = UDim.new(0, 16)
pad.Parent = scroll
stack(scroll)

local intro = block(scroll, 1)
local introTitle = label(intro, 28, 20)
introTitle.Text = Text.get("inspection.intro.title")
local introBody = label(intro, 64, 15)
introBody.Text = Text.get("inspection.intro.body")
local start = button(row(intro, 46), "Start", 1, "start", "none")
start.Text = Text.get("inspection.start")
-- 결과는 맨 위: 도장 바로 아래에 다음/쉬기를 두어 짧은 화면에서도 스크롤 없이 닿는다.
local resultPanel = block(scroll, 2)
local stamp = label(resultPanel, 30, 22)
stamp.Font = Enum.Font.GothamBold
stamp.TextColor3 = TEAL
local choiceRow = row(resultPanel, 46)
local nextCase = button(choiceRow, "NextCase", 2, "next", "none")
nextCase.Text = Text.get("inspection.next")
local rest = button(choiceRow, "Rest", 2, "rest", "none")
rest.Text = Text.get("pacing.rest")
local reason = label(resultPanel, 58, 15)
local mathName = label(resultPanel, 22, 15)
mathName.Font = Enum.Font.GothamBold
mathName.Text = Text.get("term.coordinate.name")
local mathMeaning = label(resultPanel, 38, 13)
mathMeaning.TextColor3 = MUTED
mathMeaning.Text = Text.get("inspection.label.meaning")
local claim = label(scroll, 42, 15)
claim.LayoutOrder = 3
claim.Text = Text.get("inspection.claim")
local questionPanel = block(scroll, 4)
-- 새 장면에서만: 앞 장면 결과에서 붙인 수학 이름을 이름 그대로 다시 보여 준다.
local reuseName = label(questionPanel, 22, 15)
reuseName.Font = Enum.Font.GothamBold
reuseName.TextColor3 = TEAL
local questionsTitle = label(questionPanel, 20, 13)
questionsTitle.TextColor3 = MUTED
questionsTitle.Text = Text.get("inspection.question.title")
local questions = row(questionPanel, 46)
local qOrigin = button(questions, "AskOrigin", 3, "ask", "origin")
local qMove = button(questions, "AskMove", 3, "ask", "move")
local qRecord = button(questions, "AskRecord", 3, "ask", "record")
-- 자료 줄은 물어본 것만 보인다. 계산한 칸을 그린 그림은 '도움'을 눌렀을 때만 보인다.
local board = block(scroll, 5)
local originLine = label(board, 24, 15)
local moveLine = label(board, 24, 15)
local recordLine = label(board, 24, 15)
-- 좌표 새 장면: 도착 기록을 가로, 세로 순서의 수 쌍 그대로 읽게 한다.
local recordPair = label(board, 26, 18)
recordPair.Font = Enum.Font.GothamBold
local helpRow = row(board, 40)
local helpButton = button(helpRow, "Help", 1, "help", "none")
helpButton.Text = Text.get("inspection.help")
local axis = label(board, 18, 12)
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
-- 접는 선: 가로 1이면 그 칸들의 중심, 1.5면 두 칸 중심 사이를 지나는 얇은 세로선. 반 칸에는 칠할 칸이 없다.
local foldLine = Instance.new("Frame")
foldLine.Name = "FoldLine"
foldLine.AnchorPoint = Vector2.new(0.5, 0)
foldLine.Size = UDim2.new(0, 3, 0, 3 * 41 + 36)
foldLine.BackgroundColor3 = LINE
foldLine.BorderSizePixel = 0
foldLine.ZIndex = 2
foldLine.Visible = false
foldLine.Parent = grid
local legend = label(board, 40, 12)
legend.TextColor3 = MUTED
legend.Text = Text.get("inspection.legend")
local feedback = label(scroll, 56, 15)
feedback.LayoutOrder = 6
feedback.TextColor3 = Color3.fromRGB(249, 203, 123)
local evidencePanel = block(scroll, 7)
local evidenceTitle = label(evidencePanel, 22, 13)
evidenceTitle.TextColor3 = MUTED
evidenceTitle.Text = Text.get("inspection.evidence.title")
local evidenceRow = row(evidencePanel, 54)
local eMatch = button(evidenceRow, "EvidenceMatch", 3, "evidence", "match")
local eMismatch = button(evidenceRow, "EvidenceMismatch", 3, "evidence", "mismatch")
local eMissing = button(evidenceRow, "EvidenceMissing", 3, "evidence", "missing")
eMissing.Text = Text.get("inspection.evidence.missing")
local verdictPanel = block(scroll, 8)
local verdictTitle = label(verdictPanel, 22, 13)
verdictTitle.TextColor3 = MUTED
verdictTitle.Text = Text.get("inspection.verdict.title")
local verdictRow = row(verdictPanel, 46)
local approve = button(verdictRow, "Approve", 3, "decide", "approve")
approve.Text = Text.get("inspection.verdict.approve")
local verify = button(verdictRow, "Verify", 3, "decide", "verify")
verify.Text = Text.get("inspection.verdict.verify")
local reject = button(verdictRow, "Reject", 3, "decide", "reject")
reject.Text = Text.get("inspection.verdict.reject")
local restPanel = block(scroll, 9)
local restBody = label(restPanel, 60, 16)
restBody.Text = Text.get("inspection.rest.body")
local resume = button(row(restPanel, 46), "Resume", 1, "resume", "none")
resume.Text = Text.get("inspection.resume")
-- 유한한 순회의 끝: 주제마다 처음 장면과 새 장면의 실제 선택 기록만 보인다(점수·효과 주장 없음).
local summaryPanel = block(scroll, 10)
local summaryTitle = label(summaryPanel, 26, 17)
summaryTitle.Font = Enum.Font.GothamBold
summaryTitle.Text = Text.get("inspection.summary.title")
local restart = button(row(summaryPanel, 46), "Restart", 1, "restart", "none")
restart.Text = Text.get("inspection.restart")
local summaryRows: {[string]: {first: TextLabel, new: TextLabel}} = {}
for _, theme in {"coordinate", "slope", "symmetry"} do
    local name = label(summaryPanel, 22, 15)
    name.Font = Enum.Font.GothamBold
    if theme == "slope" then name.Text = Text.get("term.slope.name")
    elseif theme == "symmetry" then name.Text = Text.get("inspection.label.symmetry.name")
    else name.Text = Text.get("term.coordinate.name") end
    summaryRows[theme] = {first = label(summaryPanel, 36, 13), new = label(summaryPanel, 36, 13)}
end
local summaryNote = label(summaryPanel, 40, 12)
summaryNote.TextColor3 = MUTED
summaryNote.Text = Text.get("inspection.summary.note")

local function focus(b: TextButton)
    GuiService.SelectedObject = b
end
local function enabled(b: TextButton, allowed: boolean)
    b.Active = allowed and not busy
    b.Selectable = b.Active
    b.AutoButtonColor = b.Active
    b.TextTransparency = if b.Active then 0 else 0.55
end
local function showChoice(b: TextButton, allowed: boolean, chosen: boolean)
    enabled(b, allowed)
    local outline = b:FindFirstChild("Outline") :: UIStroke
    outline.Enabled = GuiService.SelectedObject == b or chosen
end
local function reveal(target: GuiObject)
    task.delay(0.05, function()
        local top = target.AbsolutePosition.Y - scroll.AbsolutePosition.Y + scroll.CanvasPosition.Y
        scroll.CanvasPosition = Vector2.new(0, math.max(0, top - 8))
    end)
end
-- 문구 키는 글자 그대로 부른다(Harness i18n.missing_key). 주제·사건별 문구는 분기로 고른다.
local function showTheme(theme: string)
    if theme == "slope" then
        qOrigin.Text = Text.get("inspection.slope.question.origin")
        qMove.Text = Text.get("inspection.slope.question.move")
        qRecord.Text = Text.get("inspection.slope.question.record")
        eMatch.Text = Text.get("inspection.evidence.slope.match")
        eMismatch.Text = Text.get("inspection.evidence.slope.mismatch")
        legend.Text = Text.get("inspection.slope.legend")
        reuseName.Text = Text.get("term.slope.name")
    elseif theme == "symmetry" then
        qOrigin.Text = Text.get("inspection.symmetry.question.origin")
        qMove.Text = Text.get("inspection.symmetry.question.move")
        qRecord.Text = Text.get("inspection.symmetry.question.record")
        eMatch.Text = Text.get("inspection.evidence.symmetry.match")
        eMismatch.Text = Text.get("inspection.evidence.symmetry.mismatch")
        legend.Text = Text.get("inspection.symmetry.legend")
        reuseName.Text = Text.get("inspection.label.symmetry.name")
    else
        qOrigin.Text = Text.get("inspection.question.origin")
        qMove.Text = Text.get("inspection.question.move")
        qRecord.Text = Text.get("inspection.question.record")
        eMatch.Text = Text.get("inspection.evidence.match")
        eMismatch.Text = Text.get("inspection.evidence.mismatch")
        legend.Text = Text.get("inspection.legend")
        reuseName.Text = Text.get("term.coordinate.name")
    end
end
local function showCase(id: string)
    if id == "coord_drone" then
        claim.Text = Text.get("inspection.case.coord_drone.claim")
        reason.Text = Text.get("inspection.case.coord_drone.result")
    elseif id == "slope_stairs" then
        claim.Text = Text.get("inspection.case.slope_stairs.claim")
        reason.Text = Text.get("inspection.case.slope_stairs.result")
    elseif id == "slope_tank" then
        claim.Text = Text.get("inspection.case.slope_tank.claim")
        reason.Text = Text.get("inspection.case.slope_tank.result")
    elseif id == "sym_butterfly" then
        claim.Text = Text.get("inspection.case.sym_butterfly.claim")
        reason.Text = Text.get("inspection.case.sym_butterfly.result")
    elseif id == "sym_tile" then
        claim.Text = Text.get("inspection.case.sym_tile.claim")
        reason.Text = Text.get("inspection.case.sym_tile.result")
    else
        claim.Text = Text.get("inspection.claim")
        reason.Text = Text.get("inspection.result.match")
    end
end
local function showData(s: any)
    local theme = s.theme
    originLine.Visible = s.asked.origin == true
    moveLine.Visible = s.asked.move == true
    recordLine.Visible = s.asked.record == true
    if not s.origin then
        if theme == "coordinate" then originLine.Text = Text.get("inspection.origin.missing")
        else originLine.Text = Text.get("inspection.data.missing") end
    elseif theme == "slope" then originLine.Text = Text.get("inspection.slope.origin.point", {x = s.origin.x, y = s.origin.y})
    elseif theme == "symmetry" then originLine.Text = Text.get("inspection.symmetry.origin.point", {x = s.origin.x, y = s.origin.y})
    else originLine.Text = Text.get("inspection.origin.point", {x = s.origin.x, y = s.origin.y}) end
    if theme == "symmetry" then
        if s.line == nil then moveLine.Text = Text.get("inspection.data.missing")
        elseif s.line % 1 == 0 then moveLine.Text = Text.get("inspection.symmetry.line.point", {x = s.line})
        else moveLine.Text = Text.get("inspection.symmetry.line.half", {a = math.floor(s.line), b = math.floor(s.line) + 1}) end
    elseif not s.move then
        if theme == "slope" then moveLine.Text = Text.get("inspection.slope.move.missing")
        else moveLine.Text = Text.get("inspection.data.missing") end
    elseif theme == "slope" then moveLine.Text = Text.get("inspection.slope.move.point", {y = s.move.y})
    else moveLine.Text = Text.get("inspection.move.point", {x = s.move.x, y = s.move.y}) end
    local pair = theme == "coordinate" and s.stage == "new" and s.record ~= nil
    recordPair.Visible = recordLine.Visible and pair
    if pair then
        recordLine.Text = Text.get("inspection.record.pair")
        recordPair.Text = Text.get("inspection.point", {x = s.record.x, y = s.record.y})
    elseif not s.record then
        if theme == "coordinate" then recordLine.Text = Text.get("inspection.record.missing")
        else recordLine.Text = Text.get("inspection.data.missing") end
    elseif theme == "slope" then recordLine.Text = Text.get("inspection.slope.record.point", {x = s.record.x, y = s.record.y})
    elseif theme == "symmetry" then recordLine.Text = Text.get("inspection.symmetry.record.point", {x = s.record.x, y = s.record.y})
    else recordLine.Text = Text.get("inspection.record.point", {x = s.record.x, y = s.record.y}) end
end
local function paint(x: number, y: number, color: Color3): TextLabel?
    local cell = cells[tostring(x) .. ":" .. tostring(y)]
    if cell then cell.BackgroundColor3 = color end
    return cell
end
-- 주제 규칙대로 계산한 칸. 자료가 빠졌으면 계산하지 않는다.
local function calculated(s: any): (number?, number?)
    local o = s.origin
    if not o then return nil, nil end
    if s.theme == "symmetry" then
        if s.line == nil then return nil, nil end
        return 2 * s.line - o.x, o.y
    end
    local m = s.move
    if not m then return nil, nil end
    if s.theme == "slope" then
        if not s.record then return nil, nil end
        return s.record.x, o.y + m.y * (s.record.x - o.x)
    end
    return o.x + m.x, o.y + m.y
end
local function drawHelp(s: any)
    local open = s.help == true and (s.phase == "review" or s.phase == "resolved")
    axis.Visible = open
    grid.Visible = open
    legend.Visible = open
    foldLine.Visible = open and s.theme == "symmetry" and s.line ~= nil
    if not open then return end
    if foldLine.Visible then
        -- 칸 x 의 중심: (x + 0.5)/4 지점에서 칸 사이 틈(5px)의 절반만큼 왼쪽
        foldLine.Position = UDim2.new((s.line + 0.5) / 4, -2.5, 0, 0)
    end
    for y = 0, 3 do
        for x = 0, 3 do
            local cell = cells[tostring(x) .. ":" .. tostring(y)]
            cell.BackgroundColor3 = PANEL
            cell.Text = Text.get("inspection.point", {x = x, y = y})
        end
    end
    local o = s.origin
    local cx, cy = calculated(s)
    if o and cx and cy then
        if s.theme == "symmetry" then
            paint(o.x, o.y, PATH)
        elseif s.theme == "slope" then
            for i = 0, cx - o.x do paint(o.x + i, o.y + s.move.y * i, PATH) end
        else
            for x = math.min(o.x, cx), math.max(o.x, cx) do paint(x, o.y, PATH) end
            for y = math.min(o.y, cy), math.max(o.y, cy) do paint(cx, y, PATH) end
        end
        local destination = paint(cx, cy, PATH)
        if destination then destination.Text = Text.get("inspection.path.point", {x = cx, y = cy}) end
    else
        legend.Text = Text.get("inspection.help.missing")
    end
    local r = s.record
    local cell = if r then paint(r.x, r.y, RECORD) else nil
    if r and cell then
        if cx == r.x and cy == r.y then cell.Text = Text.get("inspection.match.cell", {x = r.x, y = r.y})
        else cell.Text = Text.get("inspection.record.cell", {x = r.x, y = r.y}) end
    end
end
local function showFeedback(theme: string, key: string)
    if key == "need_questions" then feedback.Text = Text.get("inspection.retry.questions")
    elseif key == "need_evidence" then feedback.Text = Text.get("inspection.retry.evidence")
    elseif key == "check_missing" then feedback.Text = Text.get("inspection.retry.missing")
    elseif theme == "slope" then
        if key == "check_match" then feedback.Text = Text.get("inspection.retry.slope.match")
        else feedback.Text = Text.get("inspection.retry.slope.mismatch") end
    elseif theme == "symmetry" then
        if key == "check_match" then feedback.Text = Text.get("inspection.retry.symmetry.match")
        else feedback.Text = Text.get("inspection.retry.symmetry.mismatch") end
    elseif key == "check_match" then feedback.Text = Text.get("inspection.retry.origin")
    else feedback.Text = Text.get("inspection.retry.record") end
end
local function showResult(s: any)
    if s.verdict == "approve" then stamp.Text = Text.get("inspection.result.approve")
    elseif s.verdict == "verify" then stamp.Text = Text.get("inspection.result.verify")
    else stamp.Text = Text.get("inspection.result.reject") end
    -- 한 사건의 새 용어는 하나: 처음 장면 결과에서 이름 붙이고, 새 장면에서는 그 이름을 다시 쓴다.
    if s.theme == "slope" then mathName.Text = Text.get("term.slope.name")
    elseif s.theme == "symmetry" then mathName.Text = Text.get("inspection.label.symmetry.name")
    else mathName.Text = Text.get("term.coordinate.name") end
    if s.stage == "new" then mathMeaning.Text = Text.get("inspection.label.reuse")
    elseif s.theme == "slope" then mathMeaning.Text = Text.get("inspection.label.slope.meaning")
    elseif s.theme == "symmetry" then mathMeaning.Text = Text.get("inspection.label.symmetry.meaning")
    else mathMeaning.Text = Text.get("inspection.label.meaning") end
    if s.index >= s.total then nextCase.Text = Text.get("inspection.finish")
    else nextCase.Text = Text.get("inspection.next") end
end
local function describe(object: TextLabel, entry: any)
    local retries = {retries = entry.retries}
    local correct = entry.first == "correct"
    -- help: 첫 선택 전에 그림 도움을 봤다 · later: 첫 선택 뒤에야 그림 도움을 열었다
    local later = entry.opened == true and not entry.help
    if entry.stage == "new" then
        if correct and entry.help then object.Text = Text.get("inspection.summary.new.correct_help")
        elseif correct then object.Text = Text.get("inspection.summary.new.correct")
        elseif entry.help then object.Text = Text.get("inspection.summary.new.retry_help", retries)
        elseif later then object.Text = Text.get("inspection.summary.new.retry_later", retries)
        else object.Text = Text.get("inspection.summary.new.retry", retries) end
    else
        if correct and entry.help then object.Text = Text.get("inspection.summary.first.correct_help")
        elseif correct then object.Text = Text.get("inspection.summary.first.correct")
        elseif entry.help then object.Text = Text.get("inspection.summary.first.retry_help", retries)
        elseif later then object.Text = Text.get("inspection.summary.first.retry_later", retries)
        else object.Text = Text.get("inspection.summary.first.retry", retries) end
    end
end
local function render()
    local phase = if state then state.phase else "ready"
    intro.Visible = phase == "ready"
    resultPanel.Visible = phase == "resolved"
    claim.Visible = phase == "review" or phase == "resolved"
    questionPanel.Visible = phase == "review"
    board.Visible = phase == "review" or phase == "resolved"
    evidencePanel.Visible = phase == "review"
    verdictPanel.Visible = phase == "review"
    restPanel.Visible = phase == "rest"
    summaryPanel.Visible = phase == "finished"
    feedback.Visible = phase == "review" and state ~= nil and state.feedback ~= nil
    local asked = if state then state.asked else {}
    local allAsked = asked.origin == true and asked.move == true and asked.record == true
    enabled(start, state ~= nil and phase == "ready")
    enabled(resume, phase == "rest")
    enabled(nextCase, phase == "resolved")
    enabled(rest, phase == "resolved")
    enabled(restart, phase == "finished")
    enabled(qOrigin, phase == "review")
    enabled(qMove, phase == "review")
    enabled(qRecord, phase == "review")
    qOrigin.TextColor3 = if asked.origin then TEAL else INK
    qMove.TextColor3 = if asked.move then TEAL else INK
    qRecord.TextColor3 = if asked.record then TEAL else INK
    reuseName.Visible = phase == "review" and state ~= nil and state.stage == "new"
    helpRow.Visible = phase == "review" and allAsked
    enabled(helpButton, phase == "review" and allAsked and state ~= nil and not state.help)
    local selected = if state then state.selected else nil
    showChoice(eMatch, phase == "review" and allAsked, selected == "match")
    showChoice(eMismatch, phase == "review" and allAsked, selected == "mismatch")
    showChoice(eMissing, phase == "review" and allAsked, selected == "missing")
    for _, b in {approve, verify, reject} do enabled(b, phase == "review" and state ~= nil and state.selected ~= nil) end
    if not state then return end
    if busy then status.Text = Text.get("inspection.sending")
    else status.Text = Text.get("inspection.tour.status", {index = state.index, total = state.total, count = state.completed}) end
    showTheme(state.theme)
    showCase(state.case)
    showData(state)
    drawHelp(state)
    if state.feedback then showFeedback(state.theme, state.feedback) end
    if phase == "resolved" then showResult(state) end
    if phase == "finished" and state.summary then
        for _, entry in state.summary do
            local slot = summaryRows[entry.theme]
            if slot then describe(if entry.stage == "new" then slot.new else slot.first, entry) end
        end
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
    local gamepad = UserInputService.GamepadEnabled
    if oldPhase ~= state.phase or oldToken ~= state.token then
        scroll.CanvasPosition = Vector2.zero
        if gamepad then
            if state.phase == "review" then focus(qOrigin)
            elseif state.phase == "resolved" then focus(nextCase)
            elseif state.phase == "rest" then focus(resume)
            elseif state.phase == "finished" then focus(restart)
            else focus(start) end
        end
    elseif event == "question_opened" and state.asked.origin and state.asked.move and state.asked.record then
        reveal(board)
        if gamepad then focus(eMatch) end
    elseif event == "evidence_selected" then
        reveal(evidencePanel)
        if gamepad then focus(approve) end
    elseif event == "help_opened" then
        reveal(grid)
    elseif event == "decision_retry" then
        reveal(feedback)
    end
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
        [Enum.KeyCode.Q] = qOrigin, [Enum.KeyCode.W] = qMove, [Enum.KeyCode.E] = qRecord, [Enum.KeyCode.H] = helpButton,
        [Enum.KeyCode.One] = eMatch, [Enum.KeyCode.Two] = eMismatch, [Enum.KeyCode.Three] = eMissing,
        [Enum.KeyCode.A] = approve, [Enum.KeyCode.S] = verify, [Enum.KeyCode.D] = reject,
        [Enum.KeyCode.N] = nextCase, [Enum.KeyCode.Space] = if state.phase == "rest" then resume else rest,
        [Enum.KeyCode.Return] = if state.phase == "finished" then restart else start,
    }
    local b = shortcuts[key.KeyCode]
    if b and b.Active and b.Parent and b.Parent:IsA("GuiObject") and b.Parent.Visible then
        local command = commands[b]
        send(command[1], command[2])
    end
end)

-- 넓은 화면: 자료 칸을 오른쪽에 세우고 카메라를 옮겨 심사대·NPC·문이 왼쪽에 보이게 한다.
-- 좁은 화면: 자료 칸을 아래에 둔다.
local camera: Camera? = nil
local cameraWatch: RBXScriptConnection? = nil
local function fixCamera()
    local current = camera
    if not current then return end
    -- 기본 카메라 스크립트가 캐릭터 생성 때 Custom 으로 되돌린다. 바꿀 때만 쓰므로 이 신호는 다시 이 함수로 한 번만 돌아온다.
    if current.CameraType ~= Enum.CameraType.Scriptable then current.CameraType = Enum.CameraType.Scriptable end
    local shift = if wide then 5 else 0
    current.CFrame = CFrame.lookAt(Vector3.new(shift, 7, 12), Vector3.new(shift, 0, -2.8))
    current.FieldOfView = 40
end
local function bindCamera()
    if cameraWatch then cameraWatch:Disconnect() end
    cameraWatch = nil
    camera = workspace.CurrentCamera
    local current = camera
    if current then
        cameraWatch = current:GetPropertyChangedSignal("CameraType"):Connect(fixCamera)
        fixCamera()
    end
end
local function layout()
    local size = gui.AbsoluteSize
    wide = size.X >= 600 and size.X >= size.Y * 1.25
    if wide then
        header.Position = UDim2.fromOffset(16, 0)
        header.Size = UDim2.new(0.42, -24, 0, 40)
        status.Position = UDim2.fromOffset(16, 40)
        status.Size = UDim2.new(0.42, -24, 0, 25)
        scroll.AnchorPoint = Vector2.new(1, 0)
        scroll.Position = UDim2.new(1, -12, 0, 8)
        scroll.Size = UDim2.new(0.56, -12, 1, -16)
        bounds.MaxSize = Vector2.new(480, 10000)
    else
        header.Position = UDim2.fromOffset(16, 0)
        header.Size = UDim2.new(1, -32, 0, 40)
        status.Position = UDim2.fromOffset(16, 40)
        status.Size = UDim2.new(1, -32, 0, 25)
        scroll.AnchorPoint = Vector2.new(0.5, 1)
        scroll.Position = UDim2.new(0.5, 0, 1, -12)
        scroll.Size = UDim2.new(1, -24, 0.74, -12)
        bounds.MaxSize = Vector2.new(760, 10000)
    end
    fixCamera()
end
workspace:GetPropertyChangedSignal("CurrentCamera"):Connect(bindCamera)
gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(layout)
bindCamera()
layout()
-- 외형 파츠는 CharacterAdded 뒤에 붙으므로 나중에 붙는 파츠도 숨긴다. 캐릭터마다 연결 하나만 둔다.
local avatarWatch: RBXScriptConnection? = nil
local function hide(part: Instance)
    if part:IsA("BasePart") then part.LocalTransparencyModifier = 1 end
end
local function hideCharacter(character: Model)
    if avatarWatch then avatarWatch:Disconnect() end
    avatarWatch = character.DescendantAdded:Connect(hide)
    for _, part in character:GetDescendants() do hide(part) end
    task.defer(fixCamera)
end
player.CharacterAdded:Connect(hideCharacter)
if player.Character then hideCharacter(player.Character) end
render()
task.spawn(function()
    while not state and gui.Parent do
        input:FireServer("sync", "none", "0")
        task.wait(0.7)
    end
    if UserInputService.GamepadEnabled then focus(start) end
end)
