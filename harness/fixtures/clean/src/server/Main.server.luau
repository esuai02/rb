--!strict
-- 원격 입력은 형식을 검사하고 쿨다운을 거친다 (INV-4)
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Cooldown = require(script.Parent.Cooldown)
local MissionService = require(script.Parent.MissionService)

local SignalRemote = Instance.new("RemoteEvent")
SignalRemote.Name = "SignalRemote"
SignalRemote.Parent = ReplicatedStorage

local GRID = 2   -- 정본 값 cv.coordinate_expression.grid — 신호판 격자 반폭

local function onSignal(player: Player, x: unknown, y: unknown)
	if typeof(x) ~= "number" or typeof(y) ~= "number" then return end
	if x < -GRID or x > GRID or y < -GRID or y > GRID then return end
	if not Cooldown.allow(player, "signal") then return end
	if MissionService.coordinateMove(player, {x = x :: number, y = y :: number}) then
		MissionService.openGate(player)
	end
end

SignalRemote.OnServerEvent:Connect(onSignal)
