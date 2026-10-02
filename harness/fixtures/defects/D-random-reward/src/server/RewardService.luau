--!strict
-- 보상은 서버만 정한다 (INV-4). 같은 미션의 같은 보상은 한 번만 (claimOnce).
local RewardService = {}

local claimed: {[string]: boolean} = {}

local function claimOnce(player: Player, key: string): boolean
	local slot = tostring(player.UserId) .. "|" .. key
	if claimed[slot] then
		return false
	end
	claimed[slot] = true
	return true
end

function RewardService.grant(player: Player, rewardId: string, missionId: string)
	if not claimOnce(player, missionId .. "|" .. rewardId) then return end
	local owned = player:FindFirstChild("OwnedRewards")
	if owned then
		owned:SetAttribute(rewardId, true)
		if math.random() < 0.1 then
			owned:SetAttribute("reward.rare_drop", true)
		end
	end
end

return RewardService
