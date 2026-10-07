--!strict
-- 월드가 플레이어의 말에 반응하는 자리 (K5 — 점수가 아니라 월드가 답한다).
-- 판정은 MissionService 가 하고 여기서는 보이는 것만 바꾼다. 글자는 넣지 않는다(INV-3).
-- 반응은 1초 안에 보인다(INV-8). 움직임을 기다리는 함수는 끝난 뒤 돌아오므로, 말은 월드 반응 뒤에 간다(INV-15).
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local Layout = require(ReplicatedStorage.Shared.Layout)

local WorldView = {}

-- 지금 할 곳 = 노랑 깜박임, 돌아온 신호 = 청록 고정. 색보다 깜박임과 멈춤이 먼저 뜻을 싣는다 (INV-9)
local GOAL = Color3.fromRGB(255, 176, 32)
local SIGNAL = Color3.fromRGB(80, 220, 255)
local PULSE = TweenInfo.new(0.55, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, -1, true)   -- 약 0.9Hz — 3Hz 깜박임 한도 아래
local SETTLE = TweenInfo.new(0.15)
local FLY = TweenInfo.new(0.5, Enum.EasingStyle.Quad, Enum.EasingDirection.InOut)
local RISE = TweenInfo.new(0.9, Enum.EasingStyle.Quad, Enum.EasingDirection.InOut)
local DWELL_SECONDS = 0.5   -- 고른 칸에 머무는 시간 — 어디에 내렸는지 볼 틈
local BEAT_SECONDS = 1.5    -- 다리가 닿은 뒤 문이 움직이기 전 한 박자 — '닿았어'가 먼저 보이게

-- 부품마다 지금 재생 중인 움직임 하나. 새 움직임이 앞의 것을 끊으므로 마지막 판정의 모습이 남는다.
local playing: {[BasePart]: Tween} = {}

local function play(target: BasePart, info: TweenInfo, props: {[string]: any}): Tween
	local previous = playing[target]
	if previous then
		previous:Cancel()
	end
	local tween = TweenService:Create(target, info, props)
	playing[target] = tween
	tween:Play()
	return tween
end

-- 끝까지 재생됐고 그사이 다른 움직임이 이 부품을 가져가지 않았으면 true
local function finished(target: BasePart, tween: Tween): boolean
	return tween.Completed:Wait() == Enum.PlaybackState.Completed and playing[target] == tween
end

local function part(root: Instance, name: string): BasePart?
	local found = root:FindFirstChild(name, true)
	return if found and found:IsA("BasePart") then found else nil
end

-- 이름으로 찾은 부품과 그 아래 부품 전부(폴더면 안의 부품). Place 가 꾸민 CityLights 도 같은 약속으로 켠다.
local function parts(root: Instance, name: string): {BasePart}
	local list: {BasePart} = {}
	local found = root:FindFirstChild(name, true)
	if not found then
		return list
	end
	if found:IsA("BasePart") then
		table.insert(list, found)
	end
	for _, item in found:GetDescendants() do
		if item:IsA("BasePart") then
			table.insert(list, item)
		end
	end
	return list
end

-- 상태 빛(WorldBuilder 가 단 StateLight)이 있으면 같은 색으로 둘레를 비춘다 — 밤에도 지금 할 곳·되살린 곳이 읽힌다 (S12)
local function glow(item: BasePart, color: Color3)
	local light = item:FindFirstChild("StateLight")
	if light and light:IsA("PointLight") then
		light.Color = color
		light.Enabled = true
	end
end

-- 지금 할 곳: 노랑으로 깜박인다. 깜박이는 곳은 늘 하나다 — MissionService 가 다음 자리로 옮긴다.
function WorldView.goal(root: Instance, name: string)
	for _, item in parts(root, name) do
		item.Material = Enum.Material.Neon
		item.Color = GOAL
		item.Transparency = 0
		glow(item, GOAL)
		play(item, PULSE, {Transparency = 0.4})
	end
end

-- 돌아온 신호: 청록으로 고정해 켠다. 같은 부품의 깜박임은 멈춘다.
function WorldView.restore(root: Instance, name: string)
	for _, item in parts(root, name) do
		item.Material = Enum.Material.Neon
		item.Color = SIGNAL
		item:SetAttribute("Lit", true)
		glow(item, SIGNAL)
		play(item, SETTLE, {Transparency = 0})
	end
end

-- 루미를 출발 칸에 두고 고른 칸으로 날린다 (cv.coordinate_expression.moves_from — 언제나 출발 칸에서)
local function launch(root: Instance, x: number, y: number): (BasePart?, Tween?)
	local lumi = part(root, "Lumi")
	if not lumi then
		return nil, nil
	end
	lumi.Position = Layout.lumiPosition(0, 0)
	return lumi, play(lumi, FLY, {Position = Layout.lumiPosition(x, y)})
end

-- 목표 칸: 날아가 그 앞에 머문다. 도착하면 true.
function WorldView.moveLumi(root: Instance, x: number, y: number): boolean
	local lumi, flight = launch(root, x, y)
	return lumi ~= nil and flight ~= nil and finished(lumi, flight)
end

-- 다른 칸: 고른 칸에 내렸다가 머문 뒤 출발 칸으로 돌아온다(resp.coordinate.other_spot). 다른 판정이 끼어들면 false.
function WorldView.visitLumi(root: Instance, x: number, y: number): boolean
	local lumi, flight = launch(root, x, y)
	if not (lumi and flight and finished(lumi, flight)) then
		return false
	end
	task.wait(DWELL_SECONDS)
	if playing[lumi] ~= flight then
		return false
	end
	return finished(lumi, play(lumi, FLY, {Position = Layout.lumiPosition(0, 0)}))
end

-- 루미가 협동 프리즘 위로 날아가 다른 쪽을 맡는다 (cv.helper_npc — 혼자 온 탐험가의 짝). 닿으면 true.
function WorldView.lumiTo(root: Instance, name: string): boolean
	local lumi, target = part(root, "Lumi"), part(root, name)
	if not (lumi and target) then
		return false
	end
	local spot = target.Position + Vector3.new(0, target.Size.Y / 2 + Layout.LUMI_STANDOFF, 0)
	return finished(lumi, play(lumi, FLY, {Position = spot}))
end

-- 두 프리즘의 빛줄기가 게이트 문턱 가운데에서 만난다 — 협동이 이어진 것을 월드가 보여 준다 (원천 설계 '두 빛줄기 합류')
function WorldView.joinBeams(root: Instance)
	local threshold = part(root, "GateThreshold")
	if not threshold then
		return
	end
	local meet = threshold:FindFirstChild("BeamMeet")
	if not meet then
		meet = Instance.new("Attachment")
		meet.Name = "BeamMeet"
		meet.Parent = threshold
	end
	for _, name in {"gate_prism_left", "gate_prism_right"} do
		local prism = part(root, name)
		if prism and not prism:FindFirstChild("SignalBeam") then
			local from = Instance.new("Attachment")
			from.Name = "BeamFrom"
			from.Position = Vector3.new(0, prism.Size.Y / 2, 0)
			from.Parent = prism
			local beam = Instance.new("Beam")
			beam.Name = "SignalBeam"
			beam.Attachment0, beam.Attachment1 = from, meet :: Attachment
			beam.Color = ColorSequence.new(SIGNAL)
			beam.LightEmission, beam.Width0, beam.Width1, beam.FaceCamera = 1, 0.6, 0.3, true
			beam.Parent = prism
		end
	end
end

-- 빛 다리 기울기 — 출발점과 가로 거리는 고정하고 끝 높이만 바꾼다 (cv.slope_choices.fixed). 끝 막대·난간이 함께 간다.
function WorldView.setBridge(root: Instance, step: number)
	local bridge = part(root, "LightBridge")
	if not bridge then
		return
	end
	bridge.Size, bridge.CFrame = Layout.bridgePlacement(step)
	local tip = bridge:FindFirstChild("BridgeEnd")
	if tip and tip:IsA("BasePart") then
		tip.CFrame = Layout.bridgeTip(step)
	end
	local railSize, leftFrame, rightFrame = Layout.bridgeRails(step)
	local left, right = bridge:FindFirstChild("BridgeRailLeft"), bridge:FindFirstChild("BridgeRailRight")
	if left and left:IsA("BasePart") and right and right:IsA("BasePart") then
		left.Size, left.CFrame = railSize, leftFrame
		right.Size, right.CFrame = railSize, rightFrame
	end
	bridge:SetAttribute("SlopeStep", step)
end

-- 다리가 닿고 한 박자 뒤 문이 켜진 불과 함께 셔터처럼 올라간다. 다 올라가면 돌아온다 — 그 뒤에 '열렸어'.
-- Open 속성: 없음 = 닫힘, false = 여는 중, true = 열림. 여는 중에 온 호출(같은 게이트를 쓰는 다른 플레이어)은 다 열릴 때까지 기다린다.
function WorldView.openGate(root: Instance)
	local gate = part(root, "CityLanguageGate")
	if not gate then
		return
	end
	if gate:GetAttribute("Open") ~= nil then
		while gate:GetAttribute("Open") ~= true do
			gate:GetAttributeChangedSignal("Open"):Wait()
		end
		return
	end
	gate:SetAttribute("Open", false)
	task.wait(BEAT_SECONDS)
	gate.CanCollide = false
	local lift = Vector3.new(0, Layout.GATE_SIZE.Y + 1, 0)
	for _, lamp in gate:GetChildren() do
		if lamp:IsA("BasePart") then
			play(lamp, RISE, {Position = lamp.Position + lift})
		end
	end
	finished(gate, play(gate, RISE, {Position = gate.Position + lift}))
	local threshold = part(root, "GateThreshold")
	local burst = if threshold then threshold:FindFirstChild("OpenBurst") else nil
	if burst and burst:IsA("ParticleEmitter") then
		burst:Emit(60)   -- 문이 다 오른 순간 문턱에서 빛 알갱이가 터진다 (S12)
	end
	gate:SetAttribute("Open", true)
end

return WorldView
