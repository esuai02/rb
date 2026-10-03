--!strict
-- 월드 치수. 격자 범위는 잠긴 Q2 정본 값(cv.coordinate_expression.grid)이고,
-- 칸 크기·높이 같은 나머지 수는 Q4 에서 정해 Play 테스트로 조정한다.
local Layout = {}

Layout.GRID_HALF = 2        -- cv.coordinate_expression.grid: x·y 모두 -2~2 (5×5)
Layout.CELL_STUDS = 4       -- 칸 한 변
Layout.WALL_THICKNESS = 1
Layout.WALL_CENTER = Vector3.new(0, 14, -24)   -- 세로 신호판 중심 = 출발 칸(0, 0)

Layout.BRIDGE_RUN = 12      -- 빛 다리 가로 거리 — cv.slope_choices.fixed 로 고정
Layout.BRIDGE_RISE_PER_STEP = 4
Layout.BRIDGE_START = Vector3.new(0, 4, -6)

Layout.GATE_CENTER = Vector3.new(0, 10, -34)
Layout.PRISM_OFFSET = 9
Layout.PORTAL_CENTER = Vector3.new(0, 4, -44)

-- 칸 좌표(x, y)의 월드 위치. 신호판이 세로 벽이라 y 가 실제 위쪽이 된다(cv.coordinate_expression.plane).
function Layout.cellPosition(x: number, y: number): Vector3
	return Layout.WALL_CENTER + Vector3.new(x * Layout.CELL_STUDS, y * Layout.CELL_STUDS, 0)
end

function Layout.cellName(x: number, y: number): string
	return "cell_" .. tostring(x) .. "_" .. tostring(y)
end

return Layout
