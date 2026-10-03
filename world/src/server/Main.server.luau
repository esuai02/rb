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

local function onSignal(player: Player, x: unknown, y: unknown)
	if typeof(x) ~= "number" or typeof(y) ~= "number" then return end
	if x < -GRID or x > GRID or y < -GRID or y > GRID then return end
	if not Cooldown.allow(player, "signal") then return end
	if MissionService.coordinateMove(player, {x = x :: number, y = y :: number}) then
		MissionService.openGate(player)
	end
end

local function onSlope(player: Player, choice: unknown)
	if typeof(choice) ~= "string" then return end
	if not Cooldown.allow(player, "slope") then return end
	if MissionService.slopeSet(player, choice :: string) then
		MissionService.openGate(player)
	end
end

-- 신호 패널은 다가가서 켠다. 거리는 서버가 다시 재고(표시용 값은 믿지 않는다, cv.rule_source), 연타는 쿨다운이 막는다.
local function onPanel(player: Player, panel: BasePart)
	local character = player.Character
	local root = if character then character:FindFirstChild("HumanoidRootPart") else nil
	if not (root and root:IsA("BasePart")) then return end
	if (root.Position - panel.Position).Magnitude > REACH then return end
	if not Cooldown.allow(player, "panel") then return end
	MissionService.activatePanel(player)
end

SignalRemote.OnServerEvent:Connect(onSignal)
SlopeRemote.OnServerEvent:Connect(onSlope)

local panelPart = world:FindFirstChild("SignalPanel", true)
if panelPart and panelPart:IsA("BasePart") then
	local prompt = panelPart:FindFirstChild("ActivatePrompt")
	if prompt and prompt:IsA("ProximityPrompt") then
		prompt.Triggered:Connect(function(player: Player)
			onPanel(player, panelPart)
		end)
	end
end
