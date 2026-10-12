--!strict
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Cooldown = require(script.Parent.Cooldown)
local MissionService = require(script.Parent.MissionService)
local Missions = require(script.Parent.Missions)
local Analytics = require(script.Parent.Analytics)
local WorldBuilder = require(script.Parent.WorldBuilder)
local InspectionRemote = Instance.new("RemoteEvent")
InspectionRemote.Name = "InspectionRemote"
InspectionRemote.Parent = ReplicatedStorage
local ResultRemote = Instance.new("RemoteEvent")
ResultRemote.Name = "ResultRemote"
ResultRemote.Parent = ReplicatedStorage
local world = WorldBuilder.build()
local desk = world:WaitForChild("Desk") :: BasePart
local REACH = 12 -- cv.server_distance.server_check_studs
local sessions: {[Player]: MissionService.Session} = {}
local function near(player: Player): boolean
    local character = player.Character
    local root = if character then character:FindFirstChild("HumanoidRootPart") else nil
    return root ~= nil and root:IsA("BasePart") and (root.Position - desk.Position).Magnitude <= REACH
end
local function log(player: Player, event: string)
    if event == "case_started" then
        Analytics.log(player, "inspection_progress", {inspection_step = "case_started"})
    elseif event == "question_opened" then
        Analytics.log(player, "inspection_progress", {inspection_step = "question_opened"})
    elseif event == "evidence_selected" then
        Analytics.log(player, "inspection_progress", {inspection_step = "evidence_selected"})
    elseif event == "decision_retry" then
        Analytics.log(player, "inspection_progress", {inspection_step = "decision_retry"})
    elseif event == "result_shown" then
        Analytics.log(player, "inspection_progress", {inspection_step = "result_shown"})
    elseif event == "next_chosen" then
        Analytics.log(player, "inspection_progress", {inspection_step = "next_chosen"})
        Analytics.log(player, "inspection_progress", {inspection_step = "case_started"})
    elseif event == "rest_chosen" then
        Analytics.log(player, "inspection_progress", {inspection_step = "rest_chosen"})
    end
end
local function onInspection(player: Player, action: unknown, detail: unknown, token: unknown)
    if typeof(action) ~= "string" or typeof(detail) ~= "string" or typeof(token) ~= "string" then return end
    if #token < 1 or #token > 10 then return end
    if action ~= "sync" and action ~= "start" and action ~= "ask" and action ~= "evidence"
        and action ~= "decide" and action ~= "next" and action ~= "rest" and action ~= "resume"
        and action ~= "help" and action ~= "restart" then return end
    if detail ~= "none" and detail ~= "origin" and detail ~= "move" and detail ~= "record"
        and detail ~= "match" and detail ~= "mismatch" and detail ~= "missing"
        and detail ~= "approve" and detail ~= "verify" and detail ~= "reject" then return end
    if not Cooldown.allow(player, action :: string) then return end
    if not near(player) then return end
    local session = sessions[player]
    if not session then
        session = MissionService.new(Missions) -- 워크숍 순회는 모든 참여자에게 같은 순서다.
        sessions[player] = session
    end
    local event = session.apply(action :: string, detail :: string, token :: string)
    ResultRemote:FireClient(player, session.snapshot(), event)
    if event then pcall(log, player, event) end
end
InspectionRemote.OnServerEvent:Connect(onInspection)
Players.PlayerRemoving:Connect(function(player: Player)
    sessions[player] = nil
    Cooldown.forget(player)
end)

-- 고정 심사대: 재생성 후에도 서버 거리 검사를 통과하는 자리로 돌아온다.
local function seat(character: Model)
    local root = character:WaitForChild("HumanoidRootPart", 10)
    local humanoid = character:WaitForChild("Humanoid", 10)
    if root and root:IsA("BasePart") then
        root.CFrame = CFrame.new(0, 3, 6)
        root.Anchored = true
    end
    if humanoid and humanoid:IsA("Humanoid") then
        humanoid.WalkSpeed = 0
        humanoid.JumpPower = 0
        humanoid.JumpHeight = 0
    end
end
local function join(player: Player)
    player.CharacterAdded:Connect(seat)
    if player.Character then task.spawn(seat, player.Character) end
end
Players.PlayerAdded:Connect(join)
for _, player in Players:GetPlayers() do join(player) end
