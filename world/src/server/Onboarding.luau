--!strict
-- 첫 5분 퍼널 중 미션 판정이 아닌 단계와 세션 이벤트 (specs/analytics/events.yaml · K5 §5).
-- 화면 쪽에서만 아는 사실(입력 방식·첫 입력·게이트를 봄)은 클라이언트가 알리고, 서버가 차례와 한 번만을 확인한 뒤 보낸다 (F10).
-- 퍼널 단계는 번호 순서대로만 보낸다 — 플랫폼은 뒤 단계가 먼저 오면 건너뛴 앞 단계를 그때 끝난 것으로 치고, 같은 단계는
-- 처음 것만 센다. 이 월드는 처음부터 게이트가 보이므로 '게이트를 봄'은 첫 입력을 보낸 뒤에 보낸다. 기록은 저장하지 않는다 (DEC-12).
--   onboarding_start · session_start — 화면이 준비됐다고 알릴 때(입력 방식과 함께)
--   character_spawned — 그 뒤 캐릭터가 있을 때
--   first_input — 화면이 첫 키·버튼·터치를 알렸거나, 걸어서 첫 목적지에 왔을 때(걸었으면 입력이 있었다)
--   gate_visible — 화면이 게이트 자리가 가리지 않고 보였다고 알렸을 때
--   movement_complete — 첫 목적지(신호 패널) 안내 거리 밖에 있다가 그 안으로 걸어왔을 때 (서버가 잰다)
--   session_end — 나갈 때, 진행 중이던 핵심 미션과 함께(다 마쳤으면 미션 없이)
local Players = game:GetService("Players")

local Analytics = require(script.Parent.Analytics)

local Onboarding = {}

local ARRIVE_STUDS = 10    -- 정본 값 cv.server_distance.prompt_activation_studs — 신호 패널 안내가 뜨는 거리
local CHECK_SECONDS = 0.5  -- 캐릭터·도착은 이 간격으로 잰다

local started: {[string]: boolean} = {}   -- 화면이 준비됐다고 알린 플레이어 — session_start 를 보냈다
local sent: {[string]: boolean} = {}      -- 플레이어|퍼널 단계 — 보냈다
local facts: {[string]: boolean} = {}     -- 플레이어|사실 — input·gate_seen·away·arrived (차례를 기다린다)
local destination: BasePart? = nil

local STEPS = {"character_spawned", "first_input", "gate_visible", "movement_complete"}
local FACTS = {"input", "gate_seen", "away", "arrived"}

local function key(player: Player, name: string): string
	return tostring(player.UserId) .. "|" .. name
end

-- 차례가 된 단계를 순서대로 보낸다 — 앞 단계의 사실이 아직이면 거기서 멈추고 기다린다
local function advance(player: Player)
	if not started[tostring(player.UserId)] then
		return
	end
	if not sent[key(player, "character_spawned")] then
		if not player.Character then
			return
		end
		sent[key(player, "character_spawned")] = true
		Analytics.funnel(player, "character_spawned", {})
	end
	if not sent[key(player, "first_input")] then
		if not facts[key(player, "input")] then
			return
		end
		sent[key(player, "first_input")] = true
		Analytics.funnel(player, "first_input", {})
	end
	if not sent[key(player, "gate_visible")] then
		if not facts[key(player, "gate_seen")] then
			return
		end
		sent[key(player, "gate_visible")] = true
		Analytics.funnel(player, "gate_visible", {})
	end
	if not sent[key(player, "movement_complete")] and facts[key(player, "arrived")] then
		sent[key(player, "movement_complete")] = true
		Analytics.funnel(player, "movement_complete", {})
	end
end

-- 첫 목적지(신호 패널)를 받아 둔다 — 걸어서 그 안내 거리까지 오면 이동 완료다
function Onboarding.bind(panel: BasePart?)
	destination = panel
end

-- 화면이 준비됐다 — 입력 방식과 함께 세션·온보딩 시작을 보낸다. 입력 방식은 정해진 셋만 받는다(분석 필드는 열거형 글자 그대로만, INV-10)
function Onboarding.ready(player: Player, input: string)
	local id = tostring(player.UserId)
	if started[id] then
		return
	end
	if input == "touch" then
		Analytics.log(player, "session_start", {input = "touch"})
		Analytics.funnel(player, "onboarding_start", {input = "touch"})
	elseif input == "gamepad" then
		Analytics.log(player, "session_start", {input = "gamepad"})
		Analytics.funnel(player, "onboarding_start", {input = "gamepad"})
	elseif input == "keyboard_mouse" then
		Analytics.log(player, "session_start", {input = "keyboard_mouse"})
		Analytics.funnel(player, "onboarding_start", {input = "keyboard_mouse"})
	else
		return
	end
	started[id] = true
	advance(player)
end

-- 화면이 알린 사실 — 첫 입력·게이트를 봄. 적어 두고, 차례가 되면 보낸다
function Onboarding.step(player: Player, step: string)
	if step == "first_input" then
		facts[key(player, "input")] = true
	elseif step == "gate_visible" then
		facts[key(player, "gate_seen")] = true
	end
	advance(player)
end

-- 나간다 — 진행 중이던 핵심 미션과 함께 session_end 를 보내고 이 판의 기록을 지운다 (시작을 알리지 않은 판은 보내지 않는다)
function Onboarding.leave(player: Player, mission: string?)
	local id = tostring(player.UserId)
	if started[id] then
		if mission == "m.signal_wake" then
			Analytics.log(player, "session_end", {mission = "m.signal_wake"})
		elseif mission == "m.signal_coordinate" then
			Analytics.log(player, "session_end", {mission = "m.signal_coordinate"})
		elseif mission == "m.signal_slope" then
			Analytics.log(player, "session_end", {mission = "m.signal_slope"})
		elseif mission == "m.gate_open" then
			Analytics.log(player, "session_end", {mission = "m.gate_open"})
		elseif mission == "m.zone_portal" then
			Analytics.log(player, "session_end", {mission = "m.zone_portal"})
		else
			Analytics.log(player, "session_end", {})   -- 핵심 미션을 다 마치고 나갔다
		end
	end
	started[id] = nil
	for _, step in STEPS do
		sent[id .. "|" .. step] = nil
	end
	for _, fact in FACTS do
		facts[id .. "|" .. fact] = nil
	end
end

-- 캐릭터가 생겼는지, 첫 목적지까지 걸어왔는지 서버가 잰다 — 스폰 자리가 이미 안내 거리 안이면 한 번 밖에 나갔다 와야 센다
task.spawn(function()
	while true do
		task.wait(CHECK_SECONDS)
		local target = destination
		for _, player in Players:GetPlayers() do
			if started[tostring(player.UserId)] then
				local character = player.Character
				local root = if character then character:FindFirstChild("HumanoidRootPart") else nil
				if target and root and root:IsA("BasePart") then
					if (root.Position - target.Position).Magnitude > ARRIVE_STUDS then
						facts[key(player, "away")] = true
					elseif facts[key(player, "away")] then
						facts[key(player, "arrived")] = true
						facts[key(player, "input")] = true   -- 걸어왔으면 입력이 있었다(화면 알림을 놓쳤어도)
					end
				end
				advance(player)
			end
		end
	end
end)

return Onboarding
