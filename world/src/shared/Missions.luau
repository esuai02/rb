--!strict
-- 미션 정본 — 잠긴 Q2 명세(specs/graph/neo-seoul-city-language-gate.graph.json)와 같아야 한다.
-- tests/test_world_source.py 가 두 곳을 대조한다. 문구는 키로만 두고 LocalizationTable 이 맡는다.
export type Mission = {
	id: string,
	core: boolean,
	requires: {string},
	goalKey: string?,
	newTerm: string?,
	targetEndSeconds: number?,
}

local Missions: {Mission} = {
	{id = "m.signal_wake", core = true, requires = {}, goalKey = "goal.signal_1", newTerm = nil, targetEndSeconds = 60},
	{id = "m.signal_coordinate", core = true, requires = {"m.signal_wake"}, goalKey = "goal.signal_2", newTerm = "term.coordinate", targetEndSeconds = 150},
	{id = "m.signal_slope", core = true, requires = {"m.signal_coordinate"}, goalKey = "goal.signal_3", newTerm = "term.slope", targetEndSeconds = 230},
	{id = "m.gate_open", core = true, requires = {"m.signal_slope"}, goalKey = "goal.portal", newTerm = nil, targetEndSeconds = 260},
	{id = "m.zone_portal", core = true, requires = {"m.gate_open"}, goalKey = "goal.portal", newTerm = nil, targetEndSeconds = 300},
	{id = "m.plaza_drone_delivery", core = false, requires = {"m.gate_open"}, goalKey = nil, newTerm = nil, targetEndSeconds = nil},
	{id = "m.plaza_partner_bridge", core = false, requires = {"m.gate_open"}, goalKey = nil, newTerm = nil, targetEndSeconds = nil},
}

return Missions
