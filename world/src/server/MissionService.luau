--!strict
-- 미션 판정은 서버가 한다 (INV-4). 클라이언트는 고른 칸·고른 표현만 보낸다.
-- 월드 반응은 WorldView 가, 보상은 RewardService 가 맡고, 여기서는 맞고 틀림과 진행 순서만 정한다.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Analytics = require(script.Parent.Analytics)
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
end

-- 나가면 기록을 지운다 — 다시 들어오면 처음부터 (DEC-12 한 판 안에서만)
Players.PlayerRemoving:Connect(function(player: Player)
	for _, mission in Missions do
		done[slot(player, mission.id)] = nil
	end
end)

local function tell(player: Player, code: string)
	local remote = results
	if remote then
		remote:FireClient(player, code)
	end
end

-- 월드와 결과 알림 통로를 받아 둔다. 서버가 만든 것만 쓴다.
function MissionService.bind(root: Instance, remote: RemoteEvent)
	world = root
	results = remote
	WorldView.lightTarget(root, TARGET_CELL.x, TARGET_CELL.y)
end

-- 신호 1 — 수학 없는 첫 월드 반응 (cv.gate_signals.signal_1)
function MissionService.activatePanel(player: Player)
	local root = world
	if not root or not ready(player, "m.signal_wake") then
		return
	end
	finish(player, "m.signal_wake")
	WorldView.lightPanel(root)
	Analytics.funnel(player, "first_interaction", {})
	tell(player, "signal_panel_lit")
end

function MissionService.coordinateMove(player: Player, cell: {x: number, y: number})
	local root = world
	if not ready(player, "m.signal_coordinate") then
		return
	end
	local reached = cell.x == TARGET_CELL.x and cell.y == TARGET_CELL.y
	if root then
		if reached then
			WorldView.moveLumi(root, cell.x, cell.y)
		else
			WorldView.resetLumi(root)
		end
	end
	if reached then
		finish(player, "m.signal_coordinate")
		Analytics.log(player, "math_attempt", {mission = "m.signal_coordinate", outcome = "target_reached"})
		Analytics.funnel(player, "first_math_success", {attempt = "first"})
		tell(player, "coordinate_reached")
	else
		Analytics.log(player, "math_attempt", {mission = "m.signal_coordinate", outcome = "other_result"})
		tell(player, "coordinate_other")
	end
end

function MissionService.slopeSet(player: Player, choice: string): boolean
	local root = world
	if not ready(player, "m.signal_slope") then
		return false
	end
	local step = SLOPE_STEPS[choice]
	local reached = step == TARGET_STEP
	if root and step then
		WorldView.setBridge(root, step)
	end
	if reached then
		finish(player, "m.signal_slope")
		Analytics.log(player, "math_attempt", {mission = "m.signal_slope", outcome = "target_reached"})
		tell(player, "slope_reached")
	else
		Analytics.log(player, "math_attempt", {mission = "m.signal_slope", outcome = "other_result"})
		tell(player, "slope_other")
	end
	return reached
end

-- 게이트 열림 — 완주한 사람 모두에게 같은 기본 보상 (cv.first_rewards)
function MissionService.openGate(player: Player)
	local root = world
	if not ready(player, "m.gate_open") then
		return
	end
	finish(player, "m.gate_open")
	if root then
		WorldView.openGate(root)
	end
	Analytics.funnel(player, "gate_opened", {play_mode = "solo_npc"})
	tell(player, "gate_opened")
	RewardService.grant(player, "reward.explorer_card", "m.gate_open")
end

function MissionService.count(): number
	return #Missions
end

return MissionService
