--!strict
-- 미션 완료 판정과 기본 보상 — 완주한 모두에게 같게 (INV-4)
local RewardService = require(script.Parent.RewardService)
local Analytics = require(script.Parent.Analytics)

local MissionService = {}

local TARGET = {x = 2, y = 1}

function MissionService.coordinateMove(player: Player, cell: {x: number, y: number}): boolean
	local reached = cell.x == TARGET.x and cell.y == TARGET.y
	if reached then
		Analytics.log(player, "math_attempt", {mission = "m.signal_coordinate", outcome = "target_reached", attempt = "first"})
	else
		Analytics.log(player, "math_attempt", {mission = "m.signal_coordinate", outcome = "other_result", attempt = "first"})
	end
	if reached then
		RewardService.grant(player, "reward.explorer_card", "m.signal_coordinate")
	end
	return reached
end

function MissionService.openGate(player: Player)
	RewardService.grant(player, "reward.explorer_card", "m.gate_open")
	RewardService.grant(player, "reward.explorer_badge", "m.gate_open")
	RewardService.grant(player, "unlock.light_rail_booster", "m.gate_open")
	Analytics.log(player, "gate_opened", {play_mode = "solo_npc"})
end

return MissionService
