--!strict
-- 분석은 서버에서만, 허용 이벤트만 보낸다 (INV-10 · specs/analytics/events.yaml)
-- 온보딩 퍼널 단계는 사용자당 한 번만 세므로 전용 함수로 보낸다 (F11)
local AnalyticsService = game:GetService("AnalyticsService")

local Analytics = {}

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

function Analytics.log(player: Player, eventName: string, fields: {[string]: string})
	AnalyticsService:LogCustomEvent(player, eventName, 1, pack(fields))
end

function Analytics.funnel(player: Player, stepName: string, fields: {[string]: string})
	AnalyticsService:LogOnboardingFunnelStepEvent(player, FUNNEL_STEPS[stepName], stepName, pack(fields))
end

return Analytics
