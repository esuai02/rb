--!strict
-- 보상은 서버만 정한다 (INV-4). 같은 미션의 같은 보상은 한 번만 (claimOnce).
-- 보상·저장 권한을 쓸 수 있는 파일은 이 하나뿐이다 — Harness 가 경로와 종류로 확인한다.
local BadgeService = game:GetService("BadgeService")

local RewardService = {}

local claimed: {[string]: boolean} = {}

local BADGE_IDS: {[string]: number} = {}   -- 배지 id 는 Place 를 만든 뒤 DEC-2 에서 채운다

local function claimOnce(player: Player, key: string): boolean
	local slot = tostring(player.UserId) .. "|" .. key
	if claimed[slot] then
		return false
	end
	claimed[slot] = true
	return true
end

-- 완주한 사람 모두에게 같은 기본 보상 (cv.first_rewards · 무작위·유료 없음 INV-12)
function RewardService.grant(player: Player, rewardId: string, missionId: string)
	if not claimOnce(player, rewardId .. "|" .. missionId) then return end
	local badge = BADGE_IDS[rewardId]
	if badge then
		BadgeService:AwardBadge(player.UserId, badge)
	end
end

return RewardService
