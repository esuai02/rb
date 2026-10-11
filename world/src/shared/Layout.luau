--!strict
-- 월드 치수. 격자 범위는 잠긴 Q2 정본 값(cv.coordinate_expression.grid)이고,
-- 칸 크기·높이 같은 나머지 수는 Q4 에서 정해 Play 테스트로 조정한다.
-- 배치: 출발점에서 보면 왼쪽 앞에 신호판·신호 패널, 정면에 빛 다리와 높은 게이트 단이 있다.
-- 신호판은 길(x = 0) 왼쪽이라 게이트를 가리지 않고, 게이트 단에는 빛 다리로만 오른다.
local Layout = {}

Layout.GRID_HALF = 2        -- cv.coordinate_expression.grid: x·y 모두 -2~2 (5×5)
Layout.CELL_STUDS = 4       -- 칸 한 변
Layout.WALL_THICKNESS = 1
Layout.WALL_CENTER = Vector3.new(-18, 12, -22)   -- 세로 신호판 중심 = 출발 칸(0, 0)
Layout.PANEL_POSITION = Vector3.new(-10, 3, -12)   -- 신호판 오른쪽 앞 바닥

Layout.BRIDGE_RUN = 12      -- 빛 다리 가로 거리 — cv.slope_choices.fixed 로 고정
Layout.BRIDGE_RISE_PER_STEP = 4
Layout.BRIDGE_WIDTH = 6        -- 45° 다리에서 떨어지지 않을 폭. 경로 탐색 캐릭터 반폭(2)을 빼고도 길이 남는다
Layout.BRIDGE_THICKNESS = 1
Layout.BRIDGE_START = Vector3.new(0, 0.5, -16)   -- 다리 출발 끝의 중심. 바닥에서 걸어 오른다 (cv.slope_choices.fixed)
Layout.BRIDGE_REACH_STEP = 3   -- 이 기울기 단계의 다리 끝이 게이트 문턱에 닿는다 (expr.slope.rise_more)

-- 기울기 단계의 다리 높은 끝(중심). 출발점과 가로 거리는 그대로, 높이만 바뀐다.
function Layout.bridgeEnd(step: number): Vector3
	return Layout.BRIDGE_START + Vector3.new(0, step * Layout.BRIDGE_RISE_PER_STEP, -Layout.BRIDGE_RUN)
end

-- 다리 판의 크기와 놓는 자리: 출발 끝은 BRIDGE_START, 높은 끝은 bridgeEnd(step)
function Layout.bridgePlacement(step: number): (Vector3, CFrame)
	local rise = step * Layout.BRIDGE_RISE_PER_STEP
	local length = math.sqrt(Layout.BRIDGE_RUN * Layout.BRIDGE_RUN + rise * rise)
	local center = Layout.BRIDGE_START + Vector3.new(0, rise / 2, -Layout.BRIDGE_RUN / 2)
	return Vector3.new(Layout.BRIDGE_WIDTH, Layout.BRIDGE_THICKNESS, length),
		CFrame.new(center) * CFrame.Angles(math.atan2(rise, Layout.BRIDGE_RUN), 0, 0)
end

-- 다리 판의 높은 끝(판과 같은 기울기). 다리 끝 막대가 여기에 붙는다.
function Layout.bridgeTip(step: number): CFrame
	local size, frame = Layout.bridgePlacement(step)
	return frame * CFrame.new(0, 0, -size.Z / 2)
end

-- 난간: 다리 양옆과 게이트 단 가장자리. 잘못 디뎌 떨어지지 않게 한다(일부러 뛰어넘을 수는 있다).
Layout.RAIL_HEIGHT = 3
Layout.RAIL_THICKNESS = 0.5

-- 다리 양옆 난간(판과 같은 기울기). 판 바깥 가장자리에 붙어 판과 함께 움직인다.
function Layout.bridgeRails(step: number): (Vector3, CFrame, CFrame)
	local size, frame = Layout.bridgePlacement(step)
	local up = (Layout.BRIDGE_THICKNESS + Layout.RAIL_HEIGHT) / 2
	local side = (Layout.BRIDGE_WIDTH + Layout.RAIL_THICKNESS) / 2
	return Vector3.new(Layout.RAIL_THICKNESS, Layout.RAIL_HEIGHT, size.Z),
		frame * CFrame.new(-side, up, 0), frame * CFrame.new(side, up, 0)
end

-- 게이트 단: 앞 윗모서리가 문턱이다. 정답 다리의 윗면 끝이 단 윗면과 같은 높이에서 만난다.
local reach = Layout.bridgeEnd(Layout.BRIDGE_REACH_STEP)
Layout.DECK_TOP = reach.Y + Layout.BRIDGE_THICKNESS / 2
Layout.DECK_FRONT_Z = reach.Z
Layout.DECK_SIZE = Vector3.new(16, Layout.DECK_TOP, 32)
Layout.DECK_CENTER = Vector3.new(0, Layout.DECK_TOP / 2, Layout.DECK_FRONT_Z - Layout.DECK_SIZE.Z / 2)

Layout.GATE_SIZE = Vector3.new(Layout.DECK_SIZE.X, 18, 1)   -- 단 너비 전체를 막는다 — 닫혀 있으면 돌아갈 길이 없다
Layout.GATE_CENTER = Vector3.new(0, Layout.DECK_TOP + Layout.GATE_SIZE.Y / 2, Layout.DECK_FRONT_Z - 3)
Layout.PRISM_OFFSET = 6     -- 협동 프리즘은 다리 출발점 양옆 바닥 — 기울기 미션 동안 닿아야 한다 (coop.gate_prisms)
Layout.PORTAL_CENTER = Vector3.new(0, Layout.DECK_TOP + 5, Layout.DECK_FRONT_Z - 22)

-- 칸 좌표(x, y)의 월드 위치. 신호판이 세로 벽이라 y 가 실제 위쪽이 된다(cv.coordinate_expression.plane).
function Layout.cellPosition(x: number, y: number): Vector3
	return Layout.WALL_CENTER + Vector3.new(x * Layout.CELL_STUDS, y * Layout.CELL_STUDS, 0)
end

-- 루미가 칸 앞에 머무는 자리. 구가 칸 앞면에 닿아 비스듬히 봐도 어느 칸인지 보인다.
Layout.LUMI_STANDOFF = 1.8

function Layout.lumiPosition(x: number, y: number): Vector3
	return Layout.cellPosition(x, y) + Vector3.new(0, 0, Layout.LUMI_STANDOFF)
end

function Layout.cellName(x: number, y: number): string
	return "cell_" .. tostring(x) .. "_" .. tostring(y)
end

return Layout
