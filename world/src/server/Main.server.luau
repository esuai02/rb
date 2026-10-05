--!strict
-- 원격 입력은 형식·범위를 처리 전에 거르고 쿨다운을 거친다 (INV-4 · content/remote_contracts.yaml)
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Cooldown = require(script.Parent.Cooldown)
local MissionService = require(script.Parent.MissionService)
local WorldBuilder = require(script.Parent.WorldBuilder)

local SignalRemote = Instance.new("RemoteEvent")
SignalRemote.Name = "SignalRemote"
SignalRemote.Parent = ReplicatedStorage

local SlopeRemote = Instance.new("RemoteEvent")
SlopeRemote.Name = "SlopeRemote"
SlopeRemote.Parent = ReplicatedStorage

local ResultRemote = Instance.new("RemoteEvent")
ResultRemote.Name = "ResultRemote"
ResultRemote.Parent = ReplicatedStorage

local GRID = 2   -- 정본 값 cv.coordinate_expression.grid — 신호판 격자 반폭
local REACH = 12   -- 정본 값 cv.server_distance.server_check_studs — 화면 프롬프트보다 넓게

local world = WorldBuilder.build()
MissionService.bind(world, ResultRemote)

local function find(name: string): BasePart?
	local found = world:FindFirstChild(name, true)
	return if found and found:IsA("BasePart") then found else nil
end

local panelPart = find("SignalPanel")
local portalPart = find("ZonePortal")

-- 거리는 서버가 다시 잰다(표시용 값은 믿지 않는다, cv.rule_source)
local function near(player: Player, target: BasePart?): boolean
	local character = player.Character
	local root = if character then character:FindFirstChild("HumanoidRootPart") else nil
	if not (target and root and root:IsA("BasePart")) then return false end
	return (root.Position - target.Position).Magnitude <= REACH
end

-- 고른 칸은 신호 패널을 켤 때 보낸다 — 패널 곁에서 온 것만 받는다. 진행 순서는 MissionService 가 확인한다.
local function onSignal(player: Player, x: unknown, y: unknown)
	if typeof(x) ~= "number" or typeof(y) ~= "number" then return end
	if x < -GRID or x > GRID or y < -GRID or y > GRID then return end
	if not near(player, panelPart) then return end
	if not Cooldown.allow(player, "signal") then return end
	MissionService.coordinateMove(player, {x = x :: number, y = y :: number})
end

local function onSlope(player: Player, choice: unknown)
	if typeof(choice) ~= "string" then return end
	if not Cooldown.allow(player, "slope") then return end
	if MissionService.slopeSet(player, choice :: string) then
		MissionService.openGate(player)
	end
end

-- 신호 패널은 다가가서 켠다. 연타는 쿨다운이 막는다.
local function onPanel(player: Player)
	if not near(player, panelPart) then return end
	if not Cooldown.allow(player, "panel") then return end
	MissionService.activatePanel(player)
end

-- 다음 구역 입구도 다가가서 들어간다. 게이트를 연 사람만 들어간다(순서는 MissionService 가 확인한다).
local function onPortal(player: Player)
	if not near(player, portalPart) then return end
	if not Cooldown.allow(player, "portal") then return end
	MissionService.enterPortal(player)
end

SignalRemote.OnServerEvent:Connect(onSignal)
SlopeRemote.OnServerEvent:Connect(onSlope)

-- 프롬프트는 서버가 직접 받는다 — 원격 입력이 아니라 서버가 잰 근접 상호작용이다.
-- 처리 함수는 이름으로 바로 연결한다(Harness 가 보상까지 닿는 길을 따라갈 수 있게).
local panelPrompt = if panelPart then panelPart:FindFirstChildOfClass("ProximityPrompt") else nil
if panelPrompt then
	panelPrompt.Triggered:Connect(onPanel)
end
local portalPrompt = if portalPart then portalPart:FindFirstChildOfClass("ProximityPrompt") else nil
if portalPrompt then
	portalPrompt.Triggered:Connect(onPortal)
end
