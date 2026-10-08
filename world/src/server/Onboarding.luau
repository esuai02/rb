--!strict
-- 첫 5분 퍼널 중 미션 판정이 아닌 단계와 세션 이벤트 (specs/analytics/events.yaml · K5 §5).
-- 화면 쪽에서만 아는 사실(입력 방식·첫 입력·게이트가 보임)은 클라이언트가 알리고, 서버가 차례와 한 번만을 확인한 뒤 보낸다 (F10).
-- 단계마다 한 판에 한 번만 보낸다(퍼널은 사용자당 한 번만 센다, F11). 기록은 저장하지 않는다 (DEC-12).
--   onboarding_start · session_start — 화면이 준비됐다고 알릴 때(입력 방식과 함께)
--   character_spawned — 그 뒤 캐릭터가 있을 때
--   first_input — 화면이 첫 키·버튼·터치를 알릴 때. 알림이 없어도 신호 패널까지 왔으면 입력이 있었던 것으로 센다
--   gate_visible — 화면이 게이트가 가리지 않고 처음 보였다고 알릴 때
--   movement_complete — 첫 목적지(신호 패널)의 안내가 뜨는 거리까지 걸어왔을 때 (서버가 잰다)
--   session_end — 나갈 때, 진행 중이던 핵심 미션과 함께(다 마쳤으면 미션 없이)
local Players = game:GetService("Players")

local Analytics = require(script.Parent.Analytics)

local Onboarding = {}

local ARRIVE_STUDS = 10    -- 정본 값 cv.server_distance.prompt_activation_studs — 신호 패널 안내가 뜨는 거리
local CHECK_SECONDS = 0.5  -- 도착은 이 간격으로 잰다

local started: {[string]: boolean} = {}   -- 화면이 준비됐다고 알린 플레이어 — session_start 를 보냈다
local sent: {[string]: boolean} = {}      -- 플레이어|단계 — 한 판에 한 번
local destination: BasePart? = nil

local function once(player: Player, step: string): boolean
	local slot = tostring(player.UserId) .. "|" .. step
	if sent[slot] then
		return false
	end
	sent[slot] = true
	return true
end

local function spawned(player: Player)
	if started[tostring(player.UserId)] and player.Character and once(player, "character_spawned") then
		Analytics.funnel(player, "character_spawned", {})
	end
end

-- 첫 목적지(신호 패널)를 받아 둔다 — 걸어서 그 안내 거리까지 오면 이동 완료다
function Onboarding.bind(panel: BasePart?)
	destination = panel
end

-- 화면이 준비됐다 — 입력 방식과 함께 세션·온보딩 시작을 보낸다. 캐릭터가 이미 있으면 그것도.
-- 입력 방식은 정해진 셋만 받는다(분석 필드는 열거형 글자 그대로만, INV-10)
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
	spawned(player)
end

-- 화면이 알린 단계 — 첫 입력·게이트가 보임. 시작을 알린 뒤에만, 단계마다 한 번만
function Onboarding.step(player: Player, step: string)
	if not started[tostring(player.UserId)] then
		return
	end
	if step == "first_input" and once(player, "first_input") then
		Analytics.funnel(player, "first_input", {})
	elseif step == "gate_visible" and once(player, "gate_visible") then
		Analytics.funnel(player, "gate_visible", {})
	end
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
	for _, step in {"character_spawned", "first_input", "gate_visible", "movement_complete"} do
		sent[id .. "|" .. step] = nil
	end
end

local function watch(player: Player)
	player.CharacterAdded:Connect(function()
		spawned(player)
	end)
end

Players.PlayerAdded:Connect(watch)
for _, player in Players:GetPlayers() do   -- 이 모듈보다 먼저 들어온 플레이어
	watch(player)
end

-- 첫 목적지까지 걸어왔는가 — 서버가 캐릭터 자리를 잰다. 왔으면 입력도 있었던 것이다(화면 알림을 놓쳤어도)
task.spawn(function()
	while true do
		task.wait(CHECK_SECONDS)
		local target = destination
		if target then
			for _, player in Players:GetPlayers() do
				local character = player.Character
				local root = if character then character:FindFirstChild("HumanoidRootPart") else nil
				if started[tostring(player.UserId)] and root and root:IsA("BasePart")
					and (root.Position - target.Position).Magnitude <= ARRIVE_STUDS and once(player, "movement_complete") then
					if once(player, "first_input") then
						Analytics.funnel(player, "first_input", {})
					end
					Analytics.funnel(player, "movement_complete", {})
				end
			end
		end
	end
end)

return Onboarding
