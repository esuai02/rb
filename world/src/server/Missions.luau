--!strict
-- 워크숍 순회 팩: 주제 3개 × (처음 장면 first, 다른 상황의 새 장면 new). 정답과 근거 조건은 서버에만 둔다.
-- coordinate: record = origin + move.
-- slope: move = 오른쪽 한 칸마다 바뀌는 양 {x = 1, y = 오름}. record.y = origin.y + move.y × (record.x - origin.x).
-- symmetry: line = 세로 접는 선의 가로 위치. record = (2 × line - origin.x, origin.y).
-- 필요한 자료가 하나라도 없으면 거짓이 아니라 자료 부족(missing → verify)이다.
return {
    {id = "coord_parcel", theme = "coordinate", stage = "first",
        origin = {x = 0, y = 0}, move = {x = 2, y = 1}, record = {x = 2, y = 1}, evidence = "match", verdict = "approve"},
    {id = "coord_drone", theme = "coordinate", stage = "new",
        origin = {x = 0, y = 1}, move = {x = 3, y = 1}, record = {x = 2, y = 3}, evidence = "mismatch", verdict = "reject"},
    {id = "slope_stairs", theme = "slope", stage = "first",
        origin = {x = 0, y = 0}, move = {x = 1, y = 1}, record = {x = 3, y = 1}, evidence = "mismatch", verdict = "reject"},
    {id = "slope_tank", theme = "slope", stage = "new",
        origin = {x = 0, y = 1}, move = nil, record = {x = 2, y = 3}, evidence = "missing", verdict = "verify"},
    {id = "sym_butterfly", theme = "symmetry", stage = "first",
        origin = {x = 0, y = 2}, line = 1.5, record = {x = 3, y = 2}, evidence = "match", verdict = "approve"},
    {id = "sym_tile", theme = "symmetry", stage = "new",
        origin = {x = 0, y = 3}, line = 1, record = {x = 3, y = 3}, evidence = "mismatch", verdict = "reject"},
}
