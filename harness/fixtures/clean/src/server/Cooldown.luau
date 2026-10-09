--!strict
-- 원격 입력 쿨다운 (정본 값 cv.server_cooldown — 값은 Q4 에서 실측해 고친다)
local Cooldown = {}

local SECONDS = 0.5
local last: {[string]: number} = {}

function Cooldown.allow(player: Player, action: string): boolean
	local slot = tostring(player.UserId) .. "|" .. action
	local now = os.clock()
	if last[slot] and now - last[slot] < SECONDS then
		return false
	end
	last[slot] = now
	return true
end

return Cooldown
