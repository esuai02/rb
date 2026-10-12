-- 실제 서비스 모듈을 실행한다. Roblox Play/기기 시험은 이 검사로 대체하지 않는다.
local Service = require("../world/src/server/MissionService")
local tour = require("../world/src/server/Missions")
-- 앞서 Studio Play 로 확인한 좌표 3사건. 새 순회 서비스에서도 같은 판정이 나와야 한다.
local LEGACY = {
    {id = "parcel_a", origin = {x = 0, y = 0}, move = {x = 2, y = 1}, record = {x = 2, y = 1}, evidence = "match", verdict = "approve"},
    {id = "parcel_b", origin = {x = 0, y = 0}, move = {x = 2, y = 1}, record = {x = 1, y = 2}, evidence = "mismatch", verdict = "reject"},
    {id = "parcel_c", origin = nil, move = {x = 2, y = 1}, record = nil, evidence = "missing", verdict = "verify"},
}
local assertions = 0
local function equal(actual, expected, message)
    assertions += 1
    assert(actual == expected, (message or "different") .. ": " .. tostring(actual) .. " ~= " .. tostring(expected))
end
local function act(session, action, detail, turn)
    return session.apply(action, detail or "none", turn or session.snapshot().token)
end
local function inspect(session)
    for _, question in {"origin", "move", "record"} do
        equal(act(session, "ask", question), "question_opened")
    end
end
local function wrongEvidence(case) return if case.evidence == "match" then "mismatch" else "match" end
local function wrongVerdict(case) return if case.verdict == "approve" then "reject" else "approve" end
local function solve(session, case)
    inspect(session)
    equal(act(session, "evidence", case.evidence), "evidence_selected")
    equal(act(session, "decide", case.verdict), "result_shown", case.id)
end

-- 1. 주제마다 맞는 수학 규칙으로 서비스와 따로 다시 계산한다. 자료 부족은 거짓과 다르다.
local function expected(case)
    local o, r = case.origin, case.record
    if case.theme == "symmetry" then
        assert(case.move == nil, "symmetry uses a fold line, not a move")
        if not (o and r and case.line) then return "missing" end
        return if r.x == 2 * case.line - o.x and r.y == o.y then "match" else "mismatch"
    end
    local m = case.move
    if not (o and m and r) then return "missing" end
    if case.theme == "slope" then
        equal(m.x, 1, case.id .. ": slope move is the change for one step right")
        local steps = r.x - o.x
        assert(steps >= 2, case.id .. ": slope needs several steps so change per step matters")
        return if r.y == o.y + m.y * steps then "match" else "mismatch"
    end
    return if o.x + m.x == r.x and o.y + m.y == r.y then "match" else "mismatch"
end
local VERDICT_FOR = {match = "approve", mismatch = "reject", missing = "verify"}
for _, pack in {LEGACY, tour} do
    for _, case in pack do
        local evidence = expected(case)
        equal(case.evidence, evidence, case.id)
        equal(case.verdict, VERDICT_FOR[evidence], case.id)
    end
end
-- 순회 구조: 주제 3개, 주제마다 처음 장면 뒤에 다른 자료의 새 장면. 자료 부족 사건이 하나 이상 있다.
equal(#tour, 6)
local ids, kinds = {}, {}
for i, theme in {"coordinate", "slope", "symmetry"} do
    local first, new = tour[2 * i - 1], tour[2 * i]
    equal(first.theme, theme)
    equal(first.stage, "first")
    equal(new.theme, theme)
    equal(new.stage, "new")
    local sameStart = first.origin and new.origin and first.origin.x == new.origin.x and first.origin.y == new.origin.y
    local sameRecord = first.record and new.record and first.record.x == new.record.x and first.record.y == new.record.y
    equal(sameStart == true and sameRecord == true, false, theme .. ": new scene must use different data")
    for _, case in {first, new} do
        equal(ids[case.id], nil, "unique id")
        ids[case.id] = true
        kinds[case.evidence] = true
    end
end
equal(kinds.match and kinds.mismatch and kinds.missing, true, "tour covers match, mismatch and missing")

-- 2. 옛 좌표 3사건 회귀: 순서·재시도·쉬기·중복·지난 토큰.
do
    local session = Service.new(LEGACY)
    equal(session.snapshot().phase, "ready")
    equal(session.snapshot().verdict, nil, "answer must stay on server")
    equal(session.snapshot().origin, nil, "unasked evidence must not leak")
    equal(act(session, "next"), nil, "no forced advance")
    equal(act(session, "decide", "approve"), nil)
    equal(act(session, "start"), "case_started")
    equal(act(session, "start"), nil)
    equal(act(session, "decide", "approve"), "decision_retry")
    equal(session.snapshot().feedback, "need_questions")
    equal(act(session, "evidence", "match"), "decision_retry")
    equal(act(session, "help"), nil, "help needs the questions first")
    for i, case in LEGACY do
        equal(session.snapshot().case, case.id)
        inspect(session)
        equal(act(session, "ask", "move"), "replayed", "repeat is not a new question")
        local snapshot = session.snapshot()
        snapshot.asked.origin = false
        if snapshot.origin then snapshot.origin.x = 999 end
        equal(session.snapshot().asked.origin, true, "snapshot must not mutate server state")
        if case.origin then equal(session.snapshot().origin.x, case.origin.x) end
        equal(session.snapshot().evidence, nil, "expected evidence never leaves the server")
        equal(act(session, "decide", case.verdict), "decision_retry")
        equal(session.snapshot().feedback, "need_evidence")
        equal(act(session, "evidence", wrongEvidence(case)), "evidence_selected")
        equal(act(session, "decide", case.verdict), "decision_retry", "right stamp needs right evidence")
        equal(session.snapshot().feedback, "check_" .. wrongEvidence(case), "hint follows the student's choice")
        equal(session.snapshot().phase, "review")
        equal(session.snapshot().selected, nil, "mistake invites recheck")
        equal(session.snapshot().verdict, nil)
        equal(act(session, "evidence", case.evidence), "evidence_selected")
        equal(act(session, "decide", wrongVerdict(case)), "decision_retry", "right evidence needs right verdict")
        equal(session.snapshot().feedback, "check_" .. case.evidence)
        equal(session.snapshot().completed, i - 1, "retry does not complete")
        equal(act(session, "evidence", case.evidence), "evidence_selected")
        equal(act(session, "decide", case.verdict), "result_shown")
        equal(act(session, "decide", case.verdict), nil, "duplicate completion")
        equal(session.snapshot().completed, i)
        equal(session.snapshot().verdict, case.verdict)
        equal(session.snapshot().label, true)
        equal(act(session, "rest"), "rest_chosen")
        equal(act(session, "rest"), nil)
        equal(act(session, "next"), nil, "rest must not autoplay")
        equal(act(session, "resume"), "resumed")
        equal(act(session, "resume"), nil)
        equal(session.snapshot().completed, i, "resume must not add a completion")
        local oldTurn = session.snapshot().token
        if i < #LEGACY then
            equal(act(session, "next"), "next_chosen")
            equal(act(session, "next", "none", oldTurn), nil, "stale double tap")
            equal(act(session, "decide", case.verdict, oldTurn), nil)
            equal(session.snapshot().phase, "review")
            equal(session.snapshot().selected, nil)
            equal(session.snapshot().origin, nil)
            equal(session.snapshot().record, nil)
            equal(session.snapshot().help, false)
        else
            equal(act(session, "ask", "forged"), nil)
            equal(act(session, "decide", "forged"), nil)
            equal(act(session, "forged"), nil)
            equal(act(session, "next"), "tour_finished")
            equal(act(session, "next", "none", oldTurn), nil)
        end
    end
    equal(session.snapshot().completed, 3)
    equal(session.snapshot().phase, "finished")
end

-- 3. 첫 유효 선택·도움·다시 고르기 기록과 유한한 끝, 다음 참여자 초기화.
do
    local session = Service.new(tour)
    act(session, "start")
    equal(session.snapshot().theme, "coordinate")
    equal(session.snapshot().total, 6)
    -- 사건 1: 첫 선택 전에 도움, 첫 선택은 다른 근거, 근거 맞고 도장 다름, 그다음 해결
    inspect(session)
    equal(act(session, "help"), "help_opened")
    equal(session.snapshot().help, true)
    equal(act(session, "help"), nil, "help opens once")
    local c = tour[1]
    act(session, "evidence", wrongEvidence(c))
    equal(act(session, "decide", c.verdict), "decision_retry")
    act(session, "evidence", c.evidence)
    equal(act(session, "decide", wrongVerdict(c)), "decision_retry")
    act(session, "evidence", c.evidence)
    equal(act(session, "decide", c.verdict), "result_shown")
    equal(act(session, "help"), nil, "no help after the result")
    equal(act(session, "next"), "next_chosen")
    -- 사건 2: 도움 없이 첫 선택이 달랐고, 그 뒤에 도움을 열었다
    c = tour[2]
    inspect(session)
    equal(session.snapshot().help, false, "help resets per case")
    act(session, "evidence", wrongEvidence(c))
    act(session, "decide", c.verdict)
    equal(act(session, "help"), "help_opened")
    act(session, "evidence", c.evidence)
    equal(act(session, "decide", c.verdict), "result_shown")
    act(session, "next")
    -- 사건 3: 무효 시도(근거 없이 도장)는 첫 선택으로 세지 않는다
    c = tour[3]
    inspect(session)
    equal(act(session, "decide", c.verdict), "decision_retry")
    act(session, "evidence", c.evidence)
    equal(act(session, "decide", c.verdict), "result_shown")
    act(session, "next")
    -- 사건 4: 기울기 자료 부족. 이동 질문은 빈 자료로 열린다
    c = tour[4]
    inspect(session)
    equal(session.snapshot().move, nil, "missing rule stays missing")
    act(session, "evidence", c.evidence)
    act(session, "decide", c.verdict)
    act(session, "next")
    -- 사건 5: 대칭은 이동이 아니라 접는 선을 보낸다. 도움 뒤 첫 선택이 맞았다
    c = tour[5]
    equal(session.snapshot().line, nil, "unasked line must not leak")
    inspect(session)
    equal(session.snapshot().line, c.line)
    equal(session.snapshot().move, nil)
    act(session, "help")
    act(session, "evidence", c.evidence)
    act(session, "decide", c.verdict)
    act(session, "next")
    solve(session, tour[6])
    equal(session.snapshot().summary, nil, "no record screen before the end")
    local beforeEnd = tonumber(session.snapshot().token)
    equal(act(session, "next"), "tour_finished")
    local s = session.snapshot()
    equal(s.phase, "finished")
    equal(s.completed, 6)
    equal(s.verdict, nil)
    equal(#s.summary, 6)
    local r = s.summary
    equal(r[1].first, "incorrect"); equal(r[1].help, true); equal(r[1].opened, true); equal(r[1].retries, 2)
    equal(r[2].first, "incorrect"); equal(r[2].help, false, "help after the first choice is not prior help"); equal(r[2].opened, true); equal(r[2].retries, 1)
    equal(r[3].first, "correct"); equal(r[3].retries, 0); equal(r[3].opened, false)
    equal(r[5].first, "correct"); equal(r[5].help, true)
    for i, entry in r do
        equal(entry.completed, true)
        equal(entry.theme, tour[i].theme)
        equal(entry.stage, tour[i].stage)
    end
    r[1].first = "forged"
    equal(session.snapshot().summary[1].first, "incorrect", "summary is a copy")
    equal(act(session, "next"), nil, "the tour is finite")
    equal(act(session, "start"), nil)
    local endTurn = s.token
    equal(act(session, "restart", "none", tostring(beforeEnd)), nil, "stale restart")
    equal(act(session, "restart"), "restarted")
    local fresh = session.snapshot()
    equal(fresh.phase, "ready")
    equal(fresh.completed, 0)
    equal(fresh.index, 1)
    equal(fresh.summary, nil)
    equal(fresh.label, false)
    assert(tonumber(fresh.token) > tonumber(endTurn), "token keeps rising after restart")
    equal(act(session, "start", "none", endTurn), nil, "previous participant's screen is rejected")
    equal(act(session, "start"), "case_started")
    solve(session, tour[1])
    act(session, "next")
    for i = 2, 6 do
        solve(session, tour[i])
        act(session, "next")
    end
    equal(session.snapshot().phase, "finished")
    equal(session.snapshot().summary[1].first, "correct", "next participant starts with clean records")
    equal(session.snapshot().summary[1].retries, 0)
end

-- 4. 동시에 들어온 두 사람은 질문·도움·완료·기록을 공유하지 않는다.
local left, right = Service.new(tour), Service.new(tour)
act(left, "start")
act(right, "start")
act(left, "ask", "origin")
equal(right.snapshot().asked.origin, nil)
inspect(right)
act(right, "help")
equal(left.snapshot().help, false)
act(right, "evidence", tour[1].evidence)
act(right, "decide", tour[1].verdict)
equal(left.snapshot().completed, 0)
equal(left.snapshot().phase, "review")
equal(right.snapshot().completed, 1)
print("PASS inspection runtime: " .. tostring(assertions) .. " assertions")
