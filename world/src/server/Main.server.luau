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
local prismLeft = find("gate_prism_left")     -- 정본 값 cv.coop_switch_ids
local prismRight = find("gate_prism_right")

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

-- 다리가 문턱에 닿으면(세 신호 복구) 탐험 카드를 주고 협동 프리즘 차례다 — 게이트는 두 프리즘이 이어질 때 열린다
local function onSlope(player: Player, choice: unknown)
	if typeof(choice) ~= "string" then return end
	if not Cooldown.allow(player, "slope") then return end
	if MissionService.slopeSet(player, choice :: string) then
		MissionService.rewardSignals(player)
	end
end

-- 신호 패널은 다가가서 켠다. 연타는 쿨다운이 막는다.
local function onPanel(player: Player)
	if not near(player, panelPart) then return end
	if not Cooldown.allow(player, "panel") then return end
	MissionService.activatePanel(player)
end

-- 협동 프리즘도 다가가서 길게 누른다(0.6초 홀드는 프롬프트가 잰다). 차례·짝 찾기는 MissionService 가 한다.
local function onPrismLeft(player: Player)
	if not near(player, prismLeft) then return end
	if not Cooldown.allow(player, "prism") then return end
	MissionService.holdPrism(player, "gate_prism_left")
end

local function onPrismRight(player: Player)
	if not near(player, prismRight) then return end
	if not Cooldown.allow(player, "prism") then return end
	MissionService.holdPrism(player, "gate_prism_right")
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
local leftPrompt = if prismLeft then prismLeft:FindFirstChildOfClass("ProximityPrompt") else nil
if leftPrompt then
	leftPrompt.Triggered:Connect(onPrismLeft)
end
local rightPrompt = if prismRight then prismRight:FindFirstChildOfClass("ProximityPrompt") else nil
if rightPrompt then
	rightPrompt.Triggered:Connect(onPrismRight)
end
