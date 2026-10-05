--!strict
-- 기능 오브젝트를 서버가 만든다 (INV-4 서버 권위). 도시 외관·조명·배경 지형은 Studio Place 몫이다(DEC-8).
-- 화면에 보이는 글자는 하나도 여기서 넣지 않는다 — 번역표를 거쳐 클라이언트가 넣는다(INV-3).
local Workspace = game:GetService("Workspace")

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Layout = require(ReplicatedStorage.Shared.Layout)

local WorldBuilder = {}

-- 고정 부품. 부딪힘은 Roblox 기본값(켜짐)을 쓰고, 지나가야 하는 것(루미·포털)만 끈다.
local function anchored(name: string, size: Vector3, position: Vector3, parent: Instance): BasePart
	local part = Instance.new("Part")
	part.Name = name
	part.Size = size
	part.Position = position
	part.Anchored = true
	part.Parent = parent
	return part
end

-- 신호판: 세로 벽 + 칸 25개. 칸은 이름으로만 구분하고 글자는 붙이지 않는다.
local function buildWall(root: Instance): Instance
	local span = (Layout.GRID_HALF * 2 + 1) * Layout.CELL_STUDS
	local wall = anchored("SignalWall", Vector3.new(span, span, Layout.WALL_THICKNESS), Layout.WALL_CENTER, root)
	for x = -Layout.GRID_HALF, Layout.GRID_HALF do
		for y = -Layout.GRID_HALF, Layout.GRID_HALF do
			local cell = anchored(Layout.cellName(x, y),
				Vector3.new(Layout.CELL_STUDS - 1, Layout.CELL_STUDS - 1, Layout.WALL_THICKNESS + 1),
				Layout.cellPosition(x, y), wall)
			cell:SetAttribute("CellX", x)
			cell:SetAttribute("CellY", y)
		end
	end
	return wall
end

-- 신호 패널: 다가가서 켜는 자리. 안내 글자는 클라이언트가 번역표에서 넣는다.
local function buildPanel(root: Instance): Instance
	local panel = anchored("SignalPanel", Vector3.new(4, 6, 1), Layout.PANEL_POSITION, root)
	local prompt = Instance.new("ProximityPrompt")
	prompt.Name = "ActivatePrompt"
	prompt.RequiresLineOfSight = false
	prompt.MaxActivationDistance = 10   -- 정본 값 cv.server_distance.prompt_activation_studs
	prompt.Parent = panel
	return panel
end

-- 빛 다리: 처음에는 평평하게(기울기 0) 바닥에 놓여 게이트 문턱에 닿지 않는다 (sit.slope.bridge_low)
local function buildBridge(root: Instance): Instance
	local bridge = anchored("LightBridge", Vector3.one, Layout.BRIDGE_START, root)
	bridge.Size, bridge.CFrame = Layout.bridgePlacement(0)
	return bridge
end

-- 게이트 단: 바닥에서 뛰어오를 수 없는 높이라 빛 다리로만 오른다
local function buildDeck(root: Instance): Instance
	return anchored("GateDeck", Layout.DECK_SIZE, Layout.DECK_CENTER, root)
end

local function buildGate(root: Instance): Instance
	local gate = anchored("CityLanguageGate", Layout.GATE_SIZE, Layout.GATE_CENTER, root)
	-- 문턱: 단의 앞 윗모서리. 정답 다리 끝이 여기에 닿는다
	anchored("GateThreshold", Vector3.new(Layout.DECK_SIZE.X, 1, 2),
		Vector3.new(0, Layout.DECK_TOP - 0.5, Layout.DECK_FRONT_Z - 1), gate)
	-- 협동 프리즘 — 이름은 정본 값 cv.coop_switch_ids 와 같아야 한다
	anchored("gate_prism_left", Vector3.new(2, 4, 2),
		Vector3.new(-Layout.PRISM_OFFSET, 2, Layout.BRIDGE_START.Z - 4), gate)
	anchored("gate_prism_right", Vector3.new(2, 4, 2),
		Vector3.new(Layout.PRISM_OFFSET, 2, Layout.BRIDGE_START.Z - 4), gate)
	return gate
end

local function buildLumi(root: Instance): Instance
	local lumi = anchored("Lumi", Vector3.new(2, 2, 2), Layout.cellPosition(0, 0) + Vector3.new(0, 0, 3), root)
	lumi.CanCollide = false   -- 떠다니는 드론 — 길을 막지 않는다
	return lumi
end

local function buildPortal(root: Instance): Instance
	local portal = anchored("ZonePortal", Vector3.new(8, 10, 1), Layout.PORTAL_CENTER, root)
	portal.CanCollide = false   -- 들어가는 문 — 지나간다
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
	buildLumi(root)
	buildPortal(root)
	return root
end

return WorldBuilder
