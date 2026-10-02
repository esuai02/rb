--!strict
-- 분석은 서버에서만, 허용 이벤트만 보낸다 (INV-10 · specs/analytics/events.yaml)
local AnalyticsService = game:GetService("AnalyticsService")

local Analytics = {}

local KEYS = {
	Enum.AnalyticsCustomFieldKeys.CustomField01.Name,
	Enum.AnalyticsCustomFieldKeys.CustomField02.Name,
	Enum.AnalyticsCustomFieldKeys.CustomField03.Name,
}

function Analytics.log(player: Player, eventName: string, fields: {[string]: string})
	local custom = {}
	local n = 0
	for name, value in fields do
		n += 1
		custom[KEYS[n]] = name .. ":" .. value
	end
	AnalyticsService:LogCustomEvent(player, eventName, 1, custom)
end

return Analytics
