--!strict
-- 미션 판정은 서버가 한다 (INV-4). 클라이언트는 고른 칸·고른 단계만 보낸다.
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Analytics = require(script.Parent.Analytics)
local RewardService = require(script.Parent.RewardService)
local Missions = require(ReplicatedStorage.Shared.Missions)

local MissionService = {}

-- 정본 값 cv.coordinate_expression: 루미는 언제나 출발 칸(0, 0)에서 출발한다
local TARGET_CELL = {x = 2, y = 1}
-- 정본 값 cv.slope_choices: 출발점과 가로 거리를 고정하고 기울기만 바꾼다. 선택지는 표현 키 셋뿐이다.
local SLOPE_STEPS: {[string]: number} = {
	["expr.slope.rise_more"] = 3,
	["expr.slope.rise_less"] = 1,
	["expr.slope.flat"] = 0,
}
local TARGET_STEP = 3

local opened: {[string]: boolean} = {}

local function slot(player: Player): string
	return tostring(player.UserId)
end

function MissionService.coordinateMove(player: Player, cell: {x: number, y: number}): boolean
	local reached = cell.x == TARGET_CELL.x and cell.y == TARGET_CELL.y
	if reached then
		Analytics.log(player, "math_attempt", {mission = "m.signal_coordinate", outcome = "target_reached"})
	else
		Analytics.log(player, "math_attempt", {mission = "m.signal_coordinate", outcome = "other_result"})
	end
	return reached
end

function MissionService.slopeSet(player: Player, choice: string): boolean
	local step = SLOPE_STEPS[choice]
	local reached = step == TARGET_STEP
	if reached then
		Analytics.log(player, "math_attempt", {mission = "m.signal_slope", outcome = "target_reached"})
	else
		Analytics.log(player, "math_attempt", {mission = "m.signal_slope", outcome = "other_result"})
	end
	return reached
end

-- 게이트 열림 — 완주한 사람 모두에게 같은 기본 보상 (cv.first_rewards)
function MissionService.openGate(player: Player)
	if opened[slot(player)] then
		return
	end
	opened[slot(player)] = true
	Analytics.funnel(player, "gate_opened", {play_mode = "solo_npc"})
	RewardService.grant(player, "reward.explorer_card", "m.gate_open")
end

function MissionService.count(): number
	return #Missions
end

return MissionService
