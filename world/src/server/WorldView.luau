--!strict
-- 월드가 플레이어의 말에 반응하는 자리 (K5 — 점수가 아니라 월드가 답한다).
-- 판정은 MissionService 가 하고 여기서는 보이는 것만 바꾼다. 글자는 넣지 않는다(INV-3).
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Layout = require(ReplicatedStorage.Shared.Layout)

local WorldView = {}

local function part(root: Instance, name: string): BasePart?
	local found = root:FindFirstChild(name, true)
	return if found and found:IsA("BasePart") then found else nil
end

-- 목표 칸에 빛을 켠다 — 어디로 보내야 하는지 월드가 보여 준다
function WorldView.lightTarget(root: Instance, x: number, y: number)
	local cell = part(root, Layout.cellName(x, y))
	if cell then
		cell:SetAttribute("Lit", true)
	end
end

function WorldView.moveLumi(root: Instance, x: number, y: number)
	local lumi = part(root, "Lumi")
	if lumi then
		lumi.Position = Layout.cellPosition(x, y) + Vector3.new(0, 0, 3)
	end
end

-- 다른 칸에 내리면 출발 칸으로 돌아온다 (정본 값 cv.coordinate_expression.moves_from)
function WorldView.resetLumi(root: Instance)
	WorldView.moveLumi(root, 0, 0)
end

-- 빛 다리 기울기 — 출발점과 가로 거리는 고정하고 끝 높이만 바꾼다 (cv.slope_choices.fixed)
function WorldView.setBridge(root: Instance, step: number)
	local bridge = part(root, "LightBridge")
	if not bridge then
		return
	end
	local rise = step * Layout.BRIDGE_RISE_PER_STEP
	local angle = math.atan2(rise, Layout.BRIDGE_RUN)
	bridge.Size = Vector3.new(2, 1, math.sqrt(Layout.BRIDGE_RUN * Layout.BRIDGE_RUN + rise * rise))
	bridge.CFrame = CFrame.new(Layout.BRIDGE_START + Vector3.new(0, rise / 2, -Layout.BRIDGE_RUN / 2))
		* CFrame.Angles(angle, 0, 0)
	bridge:SetAttribute("SlopeStep", step)
end

function WorldView.openGate(root: Instance)
	local gate = part(root, "CityLanguageGate")
	if gate then
		gate:SetAttribute("Open", true)
		gate.CanCollide = false
		gate.Transparency = 0.8
	end
end

function WorldView.lightPanel(root: Instance)
	local panel = part(root, "SignalPanel")
	if panel then
		panel:SetAttribute("Lit", true)
	end
end

return WorldView
