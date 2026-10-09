--!strict
-- 협동 프리즘 판정 (coop.gate_prisms). 프리즘을 다 누르면(0.6초 홀드는 ProximityPrompt 가 잰다 — cv.hold_time)
-- 그 쪽이 '준비'가 되고, 준비는 cv.coop_sync_window(3초) 동안 산다. 두 쪽이 함께 준비되면 연결된다.
-- 함께할 탐험가가 없으면 루미(npc.signal_drone)가 바로 다른 쪽을 맡는다 (INV-9).
-- 함께할 탐험가가 있으면 '제안'이 열린다: 먼저 누른 탐험가의 준비는 기다리는 동안 살아 있고(빛 기둥 유지),
-- cv.match_wait(10초)가 지나도 짝이 없으면 루미가 맡아 바로 이어진다. 루미의 준비는 사라지지 않는다.
-- 시각·참가자를 받아서 판단만 한다 — 이 모듈을 복제해 부르면 Play 의 상태와 섞이지 않고 가짜 참가자·시각으로 시험할 수 있다.
local Coop = {}

Coop.LEFT = "gate_prism_left"     -- 정본 값 cv.coop_switch_ids
Coop.RIGHT = "gate_prism_right"
Coop.NPC = "npc.signal_drone"     -- 정본 값 cv.helper_npc
Coop.SYNC_WINDOW = 3              -- 정본 값 cv.coop_sync_window
Coop.MATCH_WAIT = 10              -- 정본 값 cv.match_wait

-- 프리즘마다 준비한 쪽(탐험가 또는 루미)과 준비한 때. 프리즘은 월드에 한 쌍뿐이다
local holder: {[string]: any} = {}
local readyAt: {[string]: number} = {}
-- 지금 열린 제안 — 짝을 기다리는 탐험가, 그가 지킨 프리즘, 제안을 연 때
local offer: {who: any, prism: string, at: number}? = nil

function Coop.other(prism: string): string
	return if prism == Coop.LEFT then Coop.RIGHT else Coop.LEFT
end

local function clear(prism: string)
	holder[prism] = nil
	readyAt[prism] = nil
end

-- 기다리는 탐험가의 준비는 제안이 끝날 때까지(루미가 날아올 몫까지) 산다
local function waiting(who: any, now: number): boolean
	local open = offer
	return open ~= nil and open.who == who and now - open.at <= Coop.MATCH_WAIT + Coop.SYNC_WINDOW
end

-- 창을 넘긴 탐험가의 준비는 사라진다(루미와 짝을 기다리는 탐험가는 빼고) — 다시 누르면 된다
local function expire(now: number)
	for _, prism in {Coop.LEFT, Coop.RIGHT} do
		local at, who = readyAt[prism], holder[prism]
		if at and who ~= Coop.NPC and not waiting(who, now) and now - at > Coop.SYNC_WINDOW then
			clear(prism)
		end
	end
	local open = offer
	if open and holder[open.prism] ~= open.who then
		offer = nil   -- 기다리던 탐험가가 손을 뗐거나 다른 쪽으로 옮겼다 — 다시 누르면 새 제안
	end
end

-- who 가 prism 을 다 눌렀다. partners = 같은 단계에서 함께할 수 있는 다른 탐험가 수.
-- 돌려주는 값: "connected"(두 쪽 준비 — 참가자 둘) · "npc"(루미가 지금 다른 쪽을 맡을 차례) ·
-- "offered"(새 제안 — 함께할 탐험가에게 한 번 알린다) · "waiting"(이미 연 제안을 기다린다) ·
-- "taken"(다른 탐험가가 이미 준비한 쪽이거나 프리즘이 아니다)
function Coop.ready(who: any, prism: string, now: number, partners: number): (string, {any})
	if prism ~= Coop.LEFT and prism ~= Coop.RIGHT then
		return "taken", {}
	end
	expire(now)
	local current = holder[prism]
	if current ~= nil and current ~= who and current ~= Coop.NPC then
		return "taken", {}
	end
	local opposite = Coop.other(prism)
	if holder[opposite] == who then   -- 한 탐험가가 두 쪽을 맡지는 못한다 — 옮겨 간 것으로 본다
		clear(opposite)
	end
	holder[prism] = who   -- 루미가 지키던 쪽을 탐험가가 누르면 탐험가가 맡는다
	readyAt[prism] = now
	local partner = holder[opposite]
	if partner ~= nil then
		Coop.reset()
		return "connected", {partner, who}
	end
	if who == Coop.NPC then
		return "waiting", {}
	end
	if partners <= 0 then
		return "npc", {}
	end
	local open = offer
	if open == nil or open.who ~= who then
		offer = {who = who, prism = prism, at = now}
		return "offered", {}
	end
	open.prism = prism
	if now - open.at >= Coop.MATCH_WAIT then
		return "npc", {}
	end
	return "waiting", {}
end

-- 제안을 연 지 cv.match_wait 가 지났고 그 탐험가가 아직 지키고 있으면 (탐험가, 그가 지킨 프리즘) — 루미가 맞은편을 맡을 때
function Coop.due(now: number): (any, string?)
	expire(now)
	local open = offer
	if open and now - open.at >= Coop.MATCH_WAIT then
		return open.who, open.prism
	end
	return nil, nil
end

-- 루미가 이미 한쪽을 지키고 있는가
function Coop.npcHolds(): boolean
	return holder[Coop.LEFT] == Coop.NPC or holder[Coop.RIGHT] == Coop.NPC
end

-- 탐험가가 나갔다 — 그가 지킨 프리즘과 연 제안을 거둔다
function Coop.remove(who: any)
	for _, prism in {Coop.LEFT, Coop.RIGHT} do
		if holder[prism] == who then
			clear(prism)
		end
	end
	local open = offer
	if open and open.who == who then
		offer = nil
	end
end

-- 이어진 뒤 처음으로 — 다음에 이 게이트를 여는 탐험가는 빈 프리즘 둘에서 시작한다
function Coop.reset()
	table.clear(holder)
	table.clear(readyAt)
	offer = nil
end

return Coop
