--!strict
-- 화면 문구는 모두 LocalizationTable 을 거친다 (INV-3 · F9). 코드에는 키만 쓴다.
-- 번역표는 저장소 정본(같은 폴더의 Localization, DEC-8)에서 바로 꺼낸다.
-- GetTranslatorForPlayerAsync 는 게시된 게임에서만 동작해서 미게시 스테이징(DEC-2)에서는 쓸 수 없다.
local Players = game:GetService("Players")

local Text = {}

local TABLE = script.Parent:WaitForChild("Localization") :: LocalizationTable

local translators: {Translator} = {}

-- 플레이어 언어 → 원본 언어(SourceLocaleId) 순서. 그 언어 열이 없으면 원본 문구를 쓴다.
local function translators_for(): {Translator}
	if #translators > 0 then
		return translators
	end
	local locales = {TABLE.SourceLocaleId}
	local player = Players.LocalPlayer
	if player and player.LocaleId ~= TABLE.SourceLocaleId then
		table.insert(locales, 1, player.LocaleId)
	end
	for _, locale in locales do
		local ok, found = pcall(function()
			return TABLE:GetTranslator(locale)
		end)
		if ok then
			table.insert(translators, found)
		end
	end
	return translators
end

-- 키 하나를 그 플레이어의 언어로. 번역을 못 얻으면 원문 표에서 찾는다.
function Text.get(key: string): string
	for _, found in translators_for() do
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
