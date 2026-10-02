--!strict
-- 화면 문구는 LocalizationTable 을 거친다 (INV-3)
local LocalizationService = game:GetService("LocalizationService")
local Players = game:GetService("Players")

local Text = {}

local localizationTable = script.Parent:WaitForChild("Localization")

function Text.get(key: string): string
	local translator = localizationTable:GetTranslator(LocalizationService.RobloxLocaleId)
	local ok, text = pcall(function()
		return translator:FormatByKey(key)
	end)
	if ok then
		return text
	end
	warn("missing localization key", key, Players.LocalPlayer)
	return key
end

return Text
