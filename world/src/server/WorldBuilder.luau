--!strict
-- 기능 오브젝트를 서버가 만든다 (INV-4 서버 권위). 도시 외관·조명·배경 지형은 Studio Place 몫이다(DEC-8).
-- 화면에 보이는 글자는 하나도 여기서 넣지 않는다 — 번역표를 거쳐 클라이언트가 넣는다(INV-3).
local Workspace = game:GetService("Workspace")

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Layout = require(ReplicatedStorage.Shared.Layout)

local WorldBuilder = {}

local function anchored(class: string, name: string, size: Vector3, position: Vector3, parent: Instance): BasePart
	local part = Instance.new("Part")
	part.Name = name
	part.Size = size
	part.Position = position
	part.Anchored = true
	part.CanCollide = false
	part.Parent = parent
	return part
end

-- 신호판: 세로 벽 + 칸 25개. 칸은 이름으로만 구분하고 글자는 붙이지 않는다.
local function buildWall(root: Instance): Instance
	local span = (Layout.GRID_HALF * 2 + 1) * Layout.CELL_STUDS
	local wall = anchored("Part", "SignalWall", Vector3.new(span, span, Layout.WALL_THICKNESS), Layout.WALL_CENTER, root)
	for x = -Layout.GRID_HALF, Layout.GRID_HALF do
		for y = -Layout.GRID_HALF, Layout.GRID_HALF do
			local cell = anchored("Part", Layout.cellName(x, y),
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
	local panel = anchored("Part", "SignalPanel", Vector3.new(4, 6, 1), Vector3.new(8, 4, -16), root)
	local prompt = Instance.new("ProximityPrompt")
	prompt.Name = "ActivatePrompt"
	prompt.RequiresLineOfSight = false
	prompt.MaxActivationDistance = 10   -- 정본 값 cv.server_distance.prompt_activation_studs
	prompt.Parent = panel
	return panel
end

local function buildBridge(root: Instance): Instance
	return anchored("Part", "LightBridge", Vector3.new(2, 1, Layout.BRIDGE_RUN), Layout.BRIDGE_START, root)
end

local function buildGate(root: Instance): Instance
	local gate = anchored("Part", "CityLanguageGate", Vector3.new(14, 18, 1), Layout.GATE_CENTER, root)
	anchored("Part", "GateThreshold", Vector3.new(14, 1, 2),
		Layout.GATE_CENTER - Vector3.new(0, 9, 0), gate)
	-- 협동 프리즘 — 이름은 정본 값 cv.coop_switch_ids 와 같아야 한다
	anchored("Part", "gate_prism_left", Vector3.new(2, 4, 2),
		Layout.GATE_CENTER + Vector3.new(-Layout.PRISM_OFFSET, -6, 0), gate)
	anchored("Part", "gate_prism_right", Vector3.new(2, 4, 2),
		Layout.GATE_CENTER + Vector3.new(Layout.PRISM_OFFSET, -6, 0), gate)
	return gate
end

local function buildLumi(root: Instance): Instance
	return anchored("Part", "Lumi", Vector3.new(2, 2, 2), Layout.cellPosition(0, 0) + Vector3.new(0, 0, 3), root)
end

local function buildPortal(root: Instance): Instance
	return anchored("Part", "ZonePortal", Vector3.new(8, 10, 1), Layout.PORTAL_CENTER, root)
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
	buildGate(root)
	buildLumi(root)
	buildPortal(root)
	return root
end

return WorldBuilder
