--!strict
-- 미션 판정은 서버가 한다 (INV-4). 클라이언트는 고른 칸·고른 표현만 보낸다.
-- 월드 반응은 WorldView 가, 보상은 RewardService 가 맡고, 여기서는 맞고 틀림과 진행 순서만 정한다.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Analytics = require(script.Parent.Analytics)
local Coop = require(script.Parent.Coop)
local RewardService = require(script.Parent.RewardService)
local WorldView = require(script.Parent.WorldView)
local Layout = require(ReplicatedStorage.Shared.Layout)
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
local TARGET_STEP = Layout.BRIDGE_REACH_STEP   -- 문턱 높이는 월드(Layout)가 정한다 — 정답과 월드가 한 값을 본다

local world: Instance? = nil
local results: RemoteEvent? = nil
-- 플레이어별로 마친 미션. 순서는 Missions 정본의 requires 가 정한다 — 차례가 아닌 입력은 무시한다 (INV-4 상태로 검증).
local done: {[string]: boolean} = {}
-- 협동 프리즘 상태는 Coop 이 가진다(프리즘이 한 쌍뿐이다). 다른 탐험가와 함께 연 사람은 duo 로 센다.
local together: {[string]: boolean} = {}
local npcFlying = false
-- 플레이어·미션별 시도 수(math_attempt·first_math_success 의 attempt)와 이미 센 힌트 단계(hint_shown)
local tries: {[string]: number} = {}
local hinted: {[string]: number} = {}
local HINT_LEVELS: {[string]: number} = {level_1 = 1, level_2 = 2, level_3 = 3}   -- 정본 열거형 hint_level
-- 힌트 단계의 때를 서버가 다시 확인한다 — 화면이 알린 단계라도 차례가 될 수 있는 때보다 이르면 세지 않는다
local readyAt: {[string]: number} = {}    -- 미션이 차례가 된 때(앞 미션을 마친 때)
local hintedAt: {[string]: number} = {}   -- 마지막으로 센 힌트 단계의 때
local HINT_IDLE_SECONDS = 10   -- 정본 값 cv.hint_ladder.first_trigger.idle_seconds — 화면 사다리와 같은 값
local HINT_SLACK_SECONDS = 2   -- 통신 지연 여유 — 화면의 10초를 서버는 8초부터 받는다

local function slot(player: Player, missionId: string): string
	return tostring(player.UserId) .. "|" .. missionId
end

-- 아직 마치지 않았고 requires 를 모두 마쳤으면 지금 할 차례다
local function ready(player: Player, missionId: string): boolean
	if done[slot(player, missionId)] then
		return false
	end
	for _, mission in Missions do
		if mission.id == missionId then
			for _, need in mission.requires do
				if not done[slot(player, need)] then
					return false
				end
			end
			return true
		end
	end
	return false
end

local function finish(player: Player, missionId: string)
	done[slot(player, missionId)] = true
	local now = os.clock()
	for _, mission in Missions do   -- 이 미션을 기다리던 미션이 지금 차례가 된다
		if table.find(mission.requires, missionId) then
			readyAt[slot(player, mission.id)] = now
		end
	end
end

-- 이 미션에서 몇 번째 시도인가
local function count(player: Player, missionId: string): number
	local at = slot(player, missionId)
	local n = (tries[at] or 0) + 1
	tries[at] = n
	return n
end

-- 분석 필드 값은 열거형 글자 그대로만 보낸다(Harness analytics.calls · INV-10) — 미션·결과·시도 순번마다 한 줄
local function logCoordinate(player: Player, reached: boolean, attempt: number)
	if reached and attempt <= 1 then
		Analytics.log(player, "math_attempt", {mission = "m.signal_coordinate", outcome = "target_reached", attempt = "first"})
	elseif reached and attempt == 2 then
		Analytics.log(player, "math_attempt", {mission = "m.signal_coordinate", outcome = "target_reached", attempt = "second"})
	elseif reached then
		Analytics.log(player, "math_attempt", {mission = "m.signal_coordinate", outcome = "target_reached", attempt = "third_or_more"})
	elseif attempt <= 1 then
		Analytics.log(player, "math_attempt", {mission = "m.signal_coordinate", outcome = "other_result", attempt = "first"})
	elseif attempt == 2 then
		Analytics.log(player, "math_attempt", {mission = "m.signal_coordinate", outcome = "other_result", attempt = "second"})
	else
		Analytics.log(player, "math_attempt", {mission = "m.signal_coordinate", outcome = "other_result", attempt = "third_or_more"})
	end
end

local function logSlope(player: Player, reached: boolean, attempt: number)
	if reached and attempt <= 1 then
		Analytics.log(player, "math_attempt", {mission = "m.signal_slope", outcome = "target_reached", attempt = "first"})
	elseif reached and attempt == 2 then
		Analytics.log(player, "math_attempt", {mission = "m.signal_slope", outcome = "target_reached", attempt = "second"})
	elseif reached then
		Analytics.log(player, "math_attempt", {mission = "m.signal_slope", outcome = "target_reached", attempt = "third_or_more"})
	elseif attempt <= 1 then
		Analytics.log(player, "math_attempt", {mission = "m.signal_slope", outcome = "other_result", attempt = "first"})
	elseif attempt == 2 then
		Analytics.log(player, "math_attempt", {mission = "m.signal_slope", outcome = "other_result", attempt = "second"})
	else
		Analytics.log(player, "math_attempt", {mission = "m.signal_slope", outcome = "other_result", attempt = "third_or_more"})
	end
end

-- 첫 성공까지 몇 번 해 보았는가 (cv.first_try.key_metrics.attempts_to_first_success)
local function logFirstSuccess(player: Player, attempt: number)
	if attempt <= 1 then
		Analytics.funnel(player, "first_math_success", {attempt = "first"})
	elseif attempt == 2 then
		Analytics.funnel(player, "first_math_success", {attempt = "second"})
	else
		Analytics.funnel(player, "first_math_success", {attempt = "third_or_more"})
	end
end

local function logHint(player: Player, missionId: string, level: number)
	if missionId == "m.signal_coordinate" and level == 1 then
		Analytics.log(player, "hint_shown", {mission = "m.signal_coordinate", hint_level = "level_1"})
	elseif missionId == "m.signal_coordinate" and level == 2 then
		Analytics.log(player, "hint_shown", {mission = "m.signal_coordinate", hint_level = "level_2"})
	elseif missionId == "m.signal_coordinate" then
		Analytics.log(player, "hint_shown", {mission = "m.signal_coordinate", hint_level = "level_3"})
	elseif level == 1 then
		Analytics.log(player, "hint_shown", {mission = "m.signal_slope", hint_level = "level_1"})
	elseif level == 2 then
		Analytics.log(player, "hint_shown", {mission = "m.signal_slope", hint_level = "level_2"})
	else
		Analytics.log(player, "hint_shown", {mission = "m.signal_slope", hint_level = "level_3"})
	end
end

-- 지금 진행 중인 핵심 미션 — 아직 마치지 않은 첫 핵심 미션. 다 마쳤으면 nil (session_end 의 mission)
function MissionService.current(player: Player): string?
	for _, mission in Missions do
		if mission.core and not done[slot(player, mission.id)] then
			return mission.id
		end
	end
	return nil
end

-- 나가면 기록을 지운다 — 다시 들어오면 처음부터 (DEC-12 한 판 안에서만). Main 이 session_end 를 보낸 뒤에 부른다
function MissionService.leave(player: Player)
	for _, mission in Missions do
		done[slot(player, mission.id)] = nil
		tries[slot(player, mission.id)] = nil
		hinted[slot(player, mission.id)] = nil
		readyAt[slot(player, mission.id)] = nil
		hintedAt[slot(player, mission.id)] = nil
	end
	together[tostring(player.UserId)] = nil
	Coop.remove(player)   -- 나간 탐험가가 지킨 프리즘·연 제안을 거둔다 — 다음 탐험가가 막히지 않게
end

-- 힌트가 한 단계 올라갔다(화면이 알린다 — 힌트 사다리는 화면이 돈다). 지금 차례인 수학 미션에서 다음 단계 하나만,
-- 그 단계가 될 수 있는 때에만 센다(hint_shown): 1단계는 다른 결과를 한 번 냈거나 미션이 차례가 된 지 10초,
-- 그다음 단계는 앞 단계에서 다시 10초(cv.hint_ladder). 미션은 서버 진행 상태로 정한다 — 화면이 말한 미션·단계를 그대로 믿지 않는다
function MissionService.hint(player: Player, level: string)
	local rank = HINT_LEVELS[level]
	local missionId = if ready(player, "m.signal_coordinate") then "m.signal_coordinate"
		elseif ready(player, "m.signal_slope") then "m.signal_slope"
		else nil
	if not rank or not missionId then
		return
	end
	local at = slot(player, missionId)
	if rank ~= (hinted[at] or 0) + 1 then
		return   -- 이미 센 단계거나 단계를 건너뛰었다
	end
	local since = if rank == 1 then readyAt[at] else hintedAt[at]
	local waited = since ~= nil and os.clock() - since >= HINT_IDLE_SECONDS - HINT_SLACK_SECONDS
	local tried = rank == 1 and (tries[at] or 0) >= 1   -- 다른 결과(성공하면 미션이 끝난다)
	if not (waited or tried) then
		return
	end
	hinted[at] = rank
	hintedAt[at] = os.clock()
	logHint(player, missionId, rank)
end

-- 나간 사람에게는 보내지 않는다 — 월드 반응을 기다리는 사이에 나갈 수 있다
local function tell(player: Player, code: string)
	local remote = results
	if remote and player.Parent then
		remote:FireClient(player, code)
	end
end

-- 월드와 결과 알림 통로를 받아 둔다. 서버가 만든 것만 쓴다. 첫 '지금 할 곳'은 신호 패널이다.
function MissionService.bind(root: Instance, remote: RemoteEvent)
	world = root
	results = remote
	WorldView.goal(root, "SignalPanel")
end

-- 신호 1 — 수학 없는 첫 월드 반응 (cv.gate_signals.signal_1): 패널이 켜지고 먼 도시 불빛·게이트 불 1 이 켜진다.
-- 다음 '지금 할 곳'은 신호 칸이다.
function MissionService.activatePanel(player: Player)
	local root = world
	if not root or not ready(player, "m.signal_wake") then
		return
	end
	finish(player, "m.signal_wake")
	WorldView.restore(root, "SignalPanel")
	WorldView.restore(root, "CityLights")
	WorldView.restore(root, "GateLamp1")
	WorldView.goal(root, Layout.cellName(TARGET_CELL.x, TARGET_CELL.y))
	Analytics.funnel(player, "first_interaction", {})
	tell(player, "signal_panel_lit")
end

-- 신호 2 — 좌표. 판정·기록은 먼저 하고, 루미가 날아간 뒤에 말한다 (월드 → 말 → 이름표, INV-15).
function MissionService.coordinateMove(player: Player, cell: {x: number, y: number})
	local root = world
	if not root or not ready(player, "m.signal_coordinate") then
		return
	end
	local attempt = count(player, "m.signal_coordinate")
	if attempt == 1 then
		Analytics.funnel(player, "first_math_action", {})   -- 첫 수학 행동 = 처음 보낸 좌표(결과와 상관없이)
	end
	if cell.x == TARGET_CELL.x and cell.y == TARGET_CELL.y then
		finish(player, "m.signal_coordinate")
		logCoordinate(player, true, attempt)
		logFirstSuccess(player, attempt)
		WorldView.moveLumi(root, cell.x, cell.y)
		WorldView.restore(root, Layout.cellName(cell.x, cell.y))
		WorldView.restore(root, "GateLamp2")
		WorldView.restore(root, "LightBridge")
		WorldView.goal(root, "GateThreshold")
		if player.Parent then   -- 이 알림을 받은 화면이 '좌표' 이름표를 2초 크게 띄운다 (루미가 나는 사이 나갔으면 보이지 않는다)
			Analytics.log(player, "label_shown", {term = "term.coordinate"})
		end
		tell(player, "coordinate_reached")   -- 끼어든 판정이 있어도 성공 말은 보낸다 — 단계가 멈추지 않게
	else
		logCoordinate(player, false, attempt)
		if WorldView.visitLumi(root, cell.x, cell.y) then   -- 밀린 '다른 결과' 말은 보내지 않는다
			tell(player, "coordinate_other")
		end
	end
end

-- 신호 3 — 기울기. 다리는 바로 바뀌고, 닿으면 문턱과 게이트 불 3 이 켜진다. 다음 '지금 할 곳'은 협동 프리즘.
function MissionService.slopeSet(player: Player, choice: string): boolean
	local root = world
	local step = SLOPE_STEPS[choice]
	if not root or not step or not ready(player, "m.signal_slope") then   -- 정해진 표현 셋이 아니면 무시한다
		return false
	end
	WorldView.setBridge(root, step)
	local attempt = count(player, "m.signal_slope")
	if step == TARGET_STEP then
		finish(player, "m.signal_slope")
		logSlope(player, true, attempt)
		WorldView.restore(root, "GateThreshold")
		WorldView.restore(root, "GateLamp3")
		WorldView.goal(root, Coop.LEFT)    -- 다음 '지금 할 곳'은 협동 프리즘 한 쌍 — 함께 비추면 게이트가 열린다
		WorldView.goal(root, Coop.RIGHT)
		Analytics.log(player, "label_shown", {term = "term.slope"})   -- 이 알림을 받은 화면이 '기울기' 이름표를 띄운다
		tell(player, "slope_reached")
		return true
	end
	logSlope(player, false, attempt)
	tell(player, "slope_other")
	return false
end

-- 탐험 카드(cv.first_rewards) — 세 신호를 다 되살린 기울기 판정이 참일 때만 부른다(Main: if slopeSet(…) then).
-- 다음 협동 프리즘은 누르기라 보상하지 않는다(INV-4). 루미가 짝이 되어 늘 끝까지 가므로 혼자 온 탐험가도 같은 보상이다(INV-9·INV-12)
function MissionService.rewardSignals(player: Player)
	RewardService.grant(player, "reward.explorer_card", "m.gate_open")
end

-- 같은 단계(게이트 열기 차례)에 있는 다른 탐험가 — 빈 프리즘을 비춰 함께하자고 알린다
local function partnersOf(player: Player): {Player}
	local list = {}
	for _, other in Players:GetPlayers() do
		if other ~= player and ready(other, "m.gate_open") then
			table.insert(list, other)
		end
	end
	return list
end

-- 두 프리즘이 이어졌다 — 함께한 탐험가마다 게이트를 연다. 둘 다 탐험가면 duo, 루미와 함께면 solo_npc
local function connect(members: {any})
	local root = world
	if root then
		WorldView.restore(root, Coop.LEFT)
		WorldView.restore(root, Coop.RIGHT)
		WorldView.joinBeams(root)
	end
	local explorers: {Player} = {}
	for _, member in members do
		if typeof(member) == "Instance" and member:IsA("Player") and member.Parent ~= nil then   -- 그 사이 나간 탐험가는 빼고
			table.insert(explorers, member)
		end
	end
	for _, explorer in explorers do
		if #explorers >= 2 then
			together[tostring(explorer.UserId)] = true
			Analytics.log(explorer, "co_play_started", {play_mode = "duo"})
		end
		task.spawn(function()
			MissionService.openGate(explorer)
		end)
	end
end

-- 루미가 다른 프리즘을 맡는다 — 날아가 닿은 뒤 그 쪽이 준비된다. 부른 탐험가가 아직 준비돼 있으면 바로 이어진다.
-- 다른 탐험가의 미션이 비행을 끊으면 한 번 더 날아간다. 그래도 끊겨도 준비는 기록한다 — 혼자 온 탐험가를 멈추지 않는다(INV-9)
local function npcTakes(prism: string, asker: Player)
	local root = world
	if not root or npcFlying or Coop.npcHolds() then
		return
	end
	npcFlying = true
	tell(asker, "npc_takes_prism")
	if not WorldView.lumiTo(root, prism) then
		WorldView.lumiTo(root, prism)
	end
	npcFlying = false
	local result, members = Coop.ready(Coop.NPC, prism, os.clock(), 0)
	WorldView.restore(root, prism)
	if result == "connected" then
		connect(members)
	end
end

-- 제안을 연 지 cv.match_wait 가 지났는지 본다 — 그 사이 프리즘을 옮겼으면 지금 지키는 쪽의 맞은편을 루미가 맡는다
local function checkOffer(asker: Player)
	local who, held = Coop.due(os.clock())
	if who == asker and held then
		npcTakes(Coop.other(held), asker)
	end
end

-- 협동 (coop.gate_prisms) — 프리즘을 다 누르면 그 쪽이 준비된다. 서버가 잰 근접 상호작용이다(거리·쿨다운은 Main).
-- 함께할 탐험가가 없으면 루미가 바로, 있으면 빈 쪽을 비춰 한 번 알리고 cv.match_wait 뒤에 루미가 맡는다 (INV-9)
function MissionService.holdPrism(player: Player, prism: string)
	local root = world
	if not root or not ready(player, "m.gate_open") then
		return
	end
	local partners = partnersOf(player)
	local result, members = Coop.ready(player, prism, os.clock(), #partners)
	if result == "taken" then
		return
	end
	WorldView.restore(root, prism)   -- 내 쪽은 청록으로 고정 — 준비 완료
	tell(player, "prism_ready")
	if result == "connected" then
		connect(members)
	elseif result == "npc" then
		task.spawn(function()
			npcTakes(Coop.other(prism), player)
		end)
	elseif result == "offered" then   -- 새 제안일 때만 알린다 — 다시 눌러도 같은 제안이면 되풀이하지 않는다
		WorldView.goal(root, Coop.other(prism))
		for _, partner in partners do
			tell(partner, "partner_waiting")
			Analytics.log(partner, "co_play_offered", {offer_source = "player_present"})
		end
		task.delay(Coop.MATCH_WAIT, function()
			checkOffer(player)
		end)
	end
end

-- 게이트 열림 — 두 프리즘이 이어질 때 부른다(connect). 협동 미션 완주 = gate_opened (specs/analytics/events.yaml).
-- 기록은 판정 때, 말은 문이 다 올라간 뒤. 보상은 이미 기울기 판정 때 줬다.
function MissionService.openGate(player: Player)
	local root = world
	if not root or not ready(player, "m.gate_open") then
		return
	end
	finish(player, "m.gate_open")
	if together[tostring(player.UserId)] then
		Analytics.funnel(player, "gate_opened", {play_mode = "duo"})
	else
		Analytics.funnel(player, "gate_opened", {play_mode = "solo_npc"})
	end
	-- 카드는 기울기 판정 때 이미 받았다(rewardSignals). 퍼널은 번호 순서(9 게이트 → 10 카드)로만 보낸다 —
	-- 10을 먼저 보내면 플랫폼이 9를 그 자리에서 끝난 것으로 쳐서, 프리즘 앞에서 나간 사람도 게이트를 연 것으로 센다
	Analytics.funnel(player, "explorer_card_earned", {})
	WorldView.openGate(root)
	if done[slot(player, "m.zone_portal")] then
		return   -- 문이 오르는 사이(1.5~2.4초) 이미 입구에 들어갔다 — 끝난 화면과 켜진 포털을 되돌리지 않는다
	end
	WorldView.goal(root, "ZonePortal")   -- 다음 '지금 할 곳'은 다음 구역 입구
	tell(player, "gate_opened")
end

-- 다음 구역 입구 (m.zone_portal). 구역 자체는 Q5 뒤(INV-2) — 이 월드는 입구까지다.
-- 들어가면 온보딩이 끝나고 멈춤 지점(계속하기·쉬기)이 열린다. 다음 미션은 저절로 시작하지 않는다(pacing.autoplay_next_mission).
function MissionService.enterPortal(player: Player)
	local root = world
	if not root or not ready(player, "m.zone_portal") then
		return
	end
	finish(player, "m.zone_portal")
	Analytics.funnel(player, "zone_portal_entered", {})
	if together[tostring(player.UserId)] then
		Analytics.funnel(player, "onboarding_complete", {play_mode = "duo"})
	else
		Analytics.funnel(player, "onboarding_complete", {play_mode = "solo_npc"})
	end
	WorldView.restore(root, "ZonePortal")
	tell(player, "zone_portal_entered")
end

function MissionService.count(): number
	return #Missions
end

return MissionService
