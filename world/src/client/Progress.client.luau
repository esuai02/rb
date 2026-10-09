--!strict
-- 첫 5분 퍼널 중 화면 쪽에서만 아는 사실을 서버에 한 번씩 알린다 — 분석은 서버가 확인한 뒤 보낸다 (F10 · specs/analytics/events.yaml).
--   ready — 이 화면이 준비됐다(입력 방식과 함께) → onboarding_start · session_start
--   first_input — 첫 키·버튼·터치(마우스를 움직이기만 한 것은 세지 않는다) → first_input
--   gate_visible — 게이트가 화면 안에 들어오고 가리는 것이 없다 → gate_visible
-- 힌트 단계는 힌트 사다리를 도는 Hud 가 알린다.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local Layout = require(ReplicatedStorage.Shared.Layout)

local ProgressRemote = ReplicatedStorage:WaitForChild("ProgressRemote")

local LOOK_SECONDS = 0.25   -- 게이트가 보이는지 이 간격으로 본다
local STICK_START = 0.5     -- 게임패드 막대를 이만큼 넘겨야 입력으로 센다

-- 입력 방식 — Hud 의 배치와 같은 기준(PreferredInput). 정해진 셋 중 하나로만 알린다
local function inputName(): string
	if UserInputService.PreferredInput == Enum.PreferredInput.Touch then
		return "touch"
	elseif UserInputService.PreferredInput == Enum.PreferredInput.Gamepad then
		return "gamepad"
	end
	return "keyboard_mouse"
end

ProgressRemote:FireServer("ready", inputName())

local inputSent = false
local function sendInput()
	if not inputSent then
		inputSent = true
		ProgressRemote:FireServer("first_input", "")
	end
end

UserInputService.InputBegan:Connect(function(input: InputObject)
	local kind = input.UserInputType
	if kind ~= Enum.UserInputType.MouseMovement and kind ~= Enum.UserInputType.Focus and kind ~= Enum.UserInputType.None then
		sendInput()
	end
end)
UserInputService.InputChanged:Connect(function(input: InputObject)
	local stick = input.KeyCode == Enum.KeyCode.Thumbstick1 or input.KeyCode == Enum.KeyCode.Thumbstick2
	if stick and input.Position.Magnitude >= STICK_START then
		sendInput()
	end
end)

-- 게이트를 봤는가 — 게이트 자리(닫힌 문의 가운데, 고정된 값)가 화면 안에 있고, 카메라에서 그 자리까지 다른 것에 가리지 않을 때.
-- 문의 지금 위치를 보지 않는다 — 누가 먼저 열면 문이 위로 올라가 나중에 들어온 사람 화면 밖에 있다
local function visible(gate: BasePart): boolean
	local camera = Workspace.CurrentCamera
	if not camera then
		return false
	end
	local spot = Layout.GATE_CENTER
	local _, onScreen = camera:WorldToViewportPoint(spot)
	if not onScreen then
		return false
	end
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	local character = Players.LocalPlayer.Character
	params.FilterDescendantsInstances = if character then {character} else {}
	local origin = camera.CFrame.Position
	local hit = Workspace:Raycast(origin, spot - origin, params)
	return hit == nil or hit.Instance == gate or hit.Instance:IsDescendantOf(gate)
end

task.spawn(function()
	local world = Workspace:WaitForChild("CityLanguageGateWorld")
	local gate: BasePart? = nil
	while true do
		if not gate then
			local found = world:FindFirstChild("CityLanguageGate", true)
			gate = if found and found:IsA("BasePart") then found else nil
		end
		if gate and visible(gate) then
			ProgressRemote:FireServer("gate_visible", "")
			return
		end
		task.wait(LOOK_SECONDS)
	end
end)
