--!strict
-- 기능 오브젝트를 서버가 만든다 (INV-4 서버 권위). 도시 외관·조명·배경 지형은 Studio Place 몫이다(DEC-8).
-- 화면에 보이는 글자는 하나도 여기서 넣지 않는다 — 번역표를 거쳐 클라이언트가 넣는다(INV-3).
-- 모양만 만든다. 켜고 깜박이는 상태는 WorldView 가 바꾼다.
local Workspace = game:GetService("Workspace")

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Layout = require(ReplicatedStorage.Shared.Layout)

local WorldBuilder = {}

-- 색은 뜻 하나에 하나. 뜻은 색만이 아니라 재질(무광/발광)·모양·깜박임이 함께 싣는다 (cv.color_meaning · INV-9).
local UNLIT = Color3.fromRGB(26, 32, 52)       -- 꺼진 구조: 벽·단·게이트 문·먼 탑
local DIM = Color3.fromRGB(78, 94, 136)        -- 아직 켜지지 않은 자리: 칸·패널·불·문턱·다리
local START = Color3.fromRGB(255, 240, 205)    -- 출발 표시: 출발 칸 원판·다리 출발점
local LUMI = Color3.fromRGB(235, 252, 255)

-- 먼 도시 탑 — 신호 1 에서 불이 켜진다(resp.signal_1.panel_lit). 자리는 출발·패널 카메라에서 보이게 둔 Q4 가설.
-- Place 가 월드를 꾸며 두면(아래 build) 그 안의 CityLights 를 켠다 — 장식은 Place, 켜는 반응은 코드(DEC-8).
local CITY_TOWERS = {
	{x = 34, z = -118, height = 44},
	{x = 48, z = -150, height = 60},
	{x = 62, z = -128, height = 38},
	{x = -112, z = -58, height = 48},
	{x = -126, z = -86, height = 64},
	{x = -118, z = -24, height = 52},
}

-- 고정 부품. 부딪힘은 Roblox 기본값(켜짐)을 쓰고, 지나가야 하는 것만 끈다.
local function anchored(name: string, size: Vector3, position: Vector3, parent: Instance): Part
	local part = Instance.new("Part")
	part.Name = name
	part.Size = size
	part.Position = position
	part.Anchored = true
	part.Parent = parent
	return part
end

local function paint(part: Part, material: Enum.Material, color: Color3): Part
	part.Material = material
	part.Color = color
	return part
end

-- 눈에만 보이는 표시(원판·막대·불) — 길을 막지 않고 그림자도 없다
local function mark(part: Part): Part
	part.CanCollide = false
	part.CastShadow = false
	return part
end

-- 신호판: 세로 벽 + 칸 25개 + 출발 칸 원판. 칸은 이름으로만 구분하고 글자는 붙이지 않는다.
local function buildWall(root: Instance): Instance
	local span = (Layout.GRID_HALF * 2 + 1) * Layout.CELL_STUDS
	local wall = paint(anchored("SignalWall", Vector3.new(span, span, Layout.WALL_THICKNESS), Layout.WALL_CENTER, root),
		Enum.Material.SmoothPlastic, UNLIT)
	for x = -Layout.GRID_HALF, Layout.GRID_HALF do
		for y = -Layout.GRID_HALF, Layout.GRID_HALF do
			local cell = paint(anchored(Layout.cellName(x, y),
				Vector3.new(Layout.CELL_STUDS - 1, Layout.CELL_STUDS - 1, Layout.WALL_THICKNESS + 1),
				Layout.cellPosition(x, y), wall), Enum.Material.SmoothPlastic, DIM)
			cell:SetAttribute("CellX", x)
			cell:SetAttribute("CellY", y)
		end
	end
	-- 출발 칸(0, 0) 앞면의 둥근 원판 — 네모 칸 가운데 하나뿐인 모양이 '출발'을 알린다
	local pad = mark(paint(anchored("StartPad", Vector3.new(0.2, 2.4, 2.4), Layout.WALL_CENTER, wall),
		Enum.Material.SmoothPlastic, START))
	pad.Shape = Enum.PartType.Cylinder
	pad.CFrame = CFrame.new(Layout.cellPosition(0, 0) + Vector3.new(0, 0, (Layout.WALL_THICKNESS + 1) / 2 + 0.1))
		* CFrame.Angles(0, math.rad(90), 0)
	return wall
end

-- 신호 패널: 다가가서 켜는 자리. 안내 글자는 클라이언트가 번역표에서 넣는다.
local function buildPanel(root: Instance): Instance
	local panel = paint(anchored("SignalPanel", Vector3.new(4, 6, 1), Layout.PANEL_POSITION, root),
		Enum.Material.SmoothPlastic, DIM)
	local prompt = Instance.new("ProximityPrompt")
	prompt.Name = "ActivatePrompt"
	prompt.RequiresLineOfSight = false
	prompt.MaxActivationDistance = 10   -- 정본 값 cv.server_distance.prompt_activation_studs
	prompt.Parent = panel
	return panel
end

-- 빛 다리: 처음에는 평평하게(기울기 0) 바닥에 놓여 게이트 문턱에 닿지 않는다 (sit.slope.bridge_low)
-- 판보다 넓은 끝 막대가 '움직이는 끝', 출발점 굴대가 '고정된 출발점'을 보인다 (cv.slope_choices.fixed)
local function buildBridge(root: Instance): Instance
	local bridge = paint(anchored("LightBridge", Vector3.one, Layout.BRIDGE_START, root), Enum.Material.SmoothPlastic, DIM)
	bridge.Size, bridge.CFrame = Layout.bridgePlacement(0)
	local tip = mark(paint(anchored("BridgeEnd", Vector3.new(Layout.BRIDGE_WIDTH + 1, 1.6, 1.2), Layout.BRIDGE_START, bridge),
		Enum.Material.SmoothPlastic, DIM))
	tip.CFrame = Layout.bridgeTip(0)
	local axle = mark(paint(anchored("BridgeStart", Vector3.new(Layout.BRIDGE_WIDTH + 1, 1.4, 1.4),
		Layout.BRIDGE_START + Vector3.new(0, 0.2, 0), root), Enum.Material.SmoothPlastic, START))
	axle.Shape = Enum.PartType.Cylinder
	return bridge
end

-- 게이트 단: 바닥에서 뛰어오를 수 없는 높이라 빛 다리로만 오른다
local function buildDeck(root: Instance): Instance
	return paint(anchored("GateDeck", Layout.DECK_SIZE, Layout.DECK_CENTER, root), Enum.Material.SmoothPlastic, UNLIT)
end

-- 게이트 문 + 신호 불 셋(켜진 수 = 돌아온 신호 수). 문이 올라갈 때 불도 함께 올라가므로 게이트의 자식은 불뿐이다.
local function buildGate(root: Instance): Instance
	local gate = paint(anchored("CityLanguageGate", Layout.GATE_SIZE, Layout.GATE_CENTER, root), Enum.Material.SmoothPlastic, UNLIT)
	for n = 1, 3 do
		local lamp = mark(paint(anchored("GateLamp" .. n, Vector3.new(0.4, 2.6, 2.6), Layout.GATE_CENTER, gate),
			Enum.Material.SmoothPlastic, DIM))
		lamp.Shape = Enum.PartType.Cylinder
		lamp.CFrame = CFrame.new((n - 2) * 4, Layout.DECK_TOP + 5, Layout.GATE_CENTER.Z + Layout.GATE_SIZE.Z / 2 + 0.2)
			* CFrame.Angles(0, math.rad(90), 0)
	end
	-- 문턱: 단 앞면에 붙은 띠(윗면 = 단 윗면). 정답 다리 끝이 여기에 닿는다
	paint(anchored("GateThreshold", Vector3.new(Layout.DECK_SIZE.X, 1, 0.4),
		Vector3.new(0, Layout.DECK_TOP - 0.5, Layout.DECK_FRONT_Z + 0.2), root), Enum.Material.SmoothPlastic, DIM)
	-- 협동 프리즘 — 이름은 정본 값 cv.coop_switch_ids 와 같아야 한다
	anchored("gate_prism_left", Vector3.new(2, 4, 2),
		Vector3.new(-Layout.PRISM_OFFSET, 2, Layout.BRIDGE_START.Z - 4), root)
	anchored("gate_prism_right", Vector3.new(2, 4, 2),
		Vector3.new(Layout.PRISM_OFFSET, 2, Layout.BRIDGE_START.Z - 4), root)
	return gate
end

local function buildCity(root: Instance): Instance
	local city = Instance.new("Folder")
	city.Name = "CityLights"
	city.Parent = root
	for _, tower in CITY_TOWERS do
		mark(paint(anchored("CityTower", Vector3.new(12, tower.height, 12),
			Vector3.new(tower.x, tower.height / 2, tower.z), city), Enum.Material.SmoothPlastic, UNLIT))
	end
	return city
end

local function buildLumi(root: Instance): Instance
	local lumi = mark(paint(anchored("Lumi", Vector3.new(1.6, 1.6, 1.6), Layout.lumiPosition(0, 0), root),
		Enum.Material.Neon, LUMI))
	lumi.Shape = Enum.PartType.Ball   -- 떠다니는 빛 구 — 네모 칸·검은 테두리 커서와 모양이 다르다
	return lumi
end

-- 다음 구역 입구: 다가가서 들어간다. 안내 글자(구역 이름)는 클라이언트가 번역표에서 넣는다.
local function buildPortal(root: Instance): Instance
	local portal = paint(anchored("ZonePortal", Vector3.new(8, 10, 1), Layout.PORTAL_CENTER, root), Enum.Material.SmoothPlastic, DIM)
	portal.CanCollide = false   -- 들어가는 문 — 지나간다
	local prompt = Instance.new("ProximityPrompt")
	prompt.Name = "EnterPrompt"
	prompt.RequiresLineOfSight = false
	prompt.MaxActivationDistance = 10   -- 정본 값 cv.server_distance.prompt_activation_studs
	prompt.Parent = portal
	return portal
end

-- 월드를 한 번만 만든다. 이미 있으면 그것을 쓴다(Place 를 사람이 꾸며 둔 경우).
function WorldBuilder.build(): Instance
	local existing = Workspace:FindFirstChild("CityLanguageGateWorld")
	if existing then
		return existing
	end
	local root = Instance.new("Folder")
	root.Name = "CityLanguageGateWorld"
	root.Parent = Workspace
	buildWall(root)
	buildPanel(root)
	buildBridge(root)
	buildDeck(root)
	buildGate(root)
	buildCity(root)
	buildLumi(root)
	buildPortal(root)
	return root
end

return WorldBuilder
