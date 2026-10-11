-- 실제 서비스 모듈을 실행한다. Roblox Play/기기 시험은 이 검사로 대체하지 않는다.
local Service = require("../world/src/server/MissionService")
local cases = require("../world/src/server/Missions")
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
-- 세 팩의 수학적 판정과 자료 부족은 별개다.
for _, case in cases do
    if case.origin and case.record then
        local matches = case.origin.x + case.move.x == case.record.x and case.origin.y + case.move.y == case.record.y
        equal(case.evidence, if matches then "match" else "mismatch")
        equal(case.verdict, if matches then "approve" else "reject")
    else
        equal(case.evidence, "missing")
        equal(case.verdict, "verify")
    end
end
for _, reverse in {false, true} do
    local session = Service.new(cases, reverse)
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
    local order = if reverse then {1, 3, 2} else {1, 2, 3}
    -- 두 차례 돌며 첫 참여/재참여의 다른 순서와 상태 초기화를 확인한다.
    for round = 1, 2 do
        for _, caseIndex in order do
            local case = cases[caseIndex]
            inspect(session)
            equal(act(session, "ask", "move"), "replayed", "repeat is not a new question")
            local snapshot = session.snapshot()
            snapshot.asked.origin = false
            if snapshot.origin then snapshot.origin.x = 999 end
            equal(session.snapshot().asked.origin, true, "snapshot must not mutate server state")
            if case.origin then equal((session.snapshot().origin :: any).x, case.origin.x) end
            equal(act(session, "decide", case.verdict), "decision_retry")
            equal(session.snapshot().feedback, "need_evidence")
            local wrongEvidence = if case.evidence == "match" then "mismatch" else "match"
            equal(act(session, "evidence", wrongEvidence), "evidence_selected")
            equal(act(session, "decide", case.verdict), "decision_retry", "right stamp needs right evidence")
            equal(session.snapshot().phase, "review")
            equal(session.snapshot().selected, nil, "mistake invites recheck")
            equal(session.snapshot().verdict, nil)
            equal(act(session, "evidence", case.evidence), "evidence_selected")
            local wrongVerdict = if case.verdict == "approve" then "reject" else "approve"
            equal(act(session, "decide", wrongVerdict), "decision_retry", "right evidence needs right verdict")
            equal(act(session, "evidence", case.evidence), "evidence_selected")
            equal(act(session, "decide", case.verdict), "result_shown")
            local count = session.snapshot().completed
            equal(act(session, "decide", case.verdict), nil, "duplicate completion")
            equal(session.snapshot().completed, count)
            equal(session.snapshot().phase, "resolved")
            equal(session.snapshot().label, true)
            equal(act(session, "rest"), "rest_chosen")
            equal(act(session, "rest"), nil)
            equal(act(session, "next"), nil, "rest must not autoplay")
            equal(act(session, "resume"), "resumed")
            equal(act(session, "resume"), nil)
            equal(session.snapshot().completed, count, "resume must not add a completion")
            local oldTurn = session.snapshot().token
            equal(act(session, "next"), "next_chosen")
            equal(act(session, "next", "none", oldTurn), nil, "stale double tap")
            equal(act(session, "decide", case.verdict, oldTurn), nil)
            equal(session.snapshot().phase, "review")
            equal(session.snapshot().selected, nil)
            equal(session.snapshot().origin, nil)
            equal(session.snapshot().record, nil)
        end
        table.insert(order, table.remove(order, 1))
    end
    equal(session.snapshot().completed, 6)
    equal(act(session, "ask", "forged"), nil)
    equal(act(session, "evidence", "forged"), nil)
    equal(act(session, "decide", "forged"), nil)
    equal(act(session, "forged"), nil)
end
-- 동시에 들어온 두 사람은 질문·자료·완료 상태를 공유하지 않는다.
local left, right = Service.new(cases, false), Service.new(cases, true)
act(left, "start")
act(right, "start")
act(left, "ask", "origin")
equal(right.snapshot().asked.origin, nil)
inspect(right)
act(right, "evidence", "match")
act(right, "decide", "approve")
equal(left.snapshot().completed, 0)
equal(left.snapshot().phase, "review")
equal(right.snapshot().completed, 1)
print("PASS inspection runtime: " .. tostring(assertions) .. " assertions")
