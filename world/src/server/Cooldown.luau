--!strict
-- 원격 입력 쿨다운 (정본 값 cv.server_cooldown — 연타·자동 반복만 막고 두 번째 정상 시도는 막지 않는다)
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

-- 나간 플레이어의 쿨다운 기록을 지운다 — 방문자가 늘어도 서버 메모리가 쌓이지 않게 (Main 의 PlayerRemoving)
function Cooldown.forget(player: Player)
	local prefix = tostring(player.UserId) .. "|"
	for slot in last do
		if string.sub(slot, 1, #prefix) == prefix then
			last[slot] = nil
		end
	end
end

return Cooldown
