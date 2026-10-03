--!strict
-- 화면 문구는 모두 LocalizationTable 을 거친다 (INV-3 · F9). 코드에는 키만 쓴다.
local LocalizationService = game:GetService("LocalizationService")
local Players = game:GetService("Players")

local Text = {}

local translator: Translator? = nil

local function translator_for(): Translator?
	if translator then
		return translator
	end
	local player = Players.LocalPlayer
	if not player then
		return nil
	end
	local ok, found = pcall(function()
		return LocalizationService:GetTranslatorForPlayerAsync(player)
	end)
	translator = if ok then found else nil
	return translator
end

-- 키 하나를 그 플레이어의 언어로. 번역을 못 얻으면 원문 표에서 찾는다.
function Text.get(key: string): string
	local found = translator_for()
	if found then
		local ok, value = pcall(function()
			return found:FormatByKey(key)
		end)
		if ok then
			return value
		end
	end
	return key
end

return Text
