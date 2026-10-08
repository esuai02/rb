--!strict
-- 분석은 서버에서만, 허용 목록(specs/analytics/events.yaml)의 이벤트만 보낸다 (INV-10 · F10)
-- 온보딩 퍼널 단계는 사용자당 한 번만 세므로 전용 함수로 보낸다 (F11)
local AnalyticsService = game:GetService("AnalyticsService")
local RunService = game:GetService("RunService")

local Analytics = {}

-- Studio 에서만 출력 창에 이벤트 이름과 필드를 적는다 — Play 시험에서 무엇이 나갔는지 확인하는 용도(라이브 서버는 적지 않는다).
-- 필드는 이미 열거형 값뿐이고 플레이어는 적지 않는다 (INV-10)
local TRACE = RunService:IsStudio()

local KEYS = {
	Enum.AnalyticsCustomFieldKeys.CustomField01.Name,
	Enum.AnalyticsCustomFieldKeys.CustomField02.Name,
	Enum.AnalyticsCustomFieldKeys.CustomField03.Name,
}

local FUNNEL_STEPS = {
	onboarding_start = 1,
	character_spawned = 2,
	first_input = 3,
	gate_visible = 4,
	movement_complete = 5,
	first_interaction = 6,
	first_math_action = 7,
	first_math_success = 8,
	gate_opened = 9,
	explorer_card_earned = 10,
	zone_portal_entered = 11,
	onboarding_complete = 12,
}

local function pack(fields: {[string]: string}): {[string]: string}
	local custom = {}
	local n = 0
	for name, value in fields do
		n += 1
		custom[KEYS[n]] = name .. ":" .. value
	end
	return custom
end

local function trace(kind: string, eventName: string, packed: {[string]: string})
	if not TRACE then
		return
	end
	local parts = {}
	for _, value in packed do
		table.insert(parts, value)
	end
	table.sort(parts)
	print("[analytics]", kind, eventName, table.concat(parts, " "))
end

function Analytics.log(player: Player, eventName: string, fields: {[string]: string})
	local packed = pack(fields)
	trace("custom", eventName, packed)
	AnalyticsService:LogCustomEvent(player, eventName, 1, packed)
end

function Analytics.funnel(player: Player, stepName: string, fields: {[string]: string})
	local packed = pack(fields)
	trace("funnel", stepName, packed)
	AnalyticsService:LogOnboardingFunnelStepEvent(player, FUNNEL_STEPS[stepName], stepName, packed)
end

return Analytics
