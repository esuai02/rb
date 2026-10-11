--!strict
-- 같은 서버 규칙을 실제 Luau로 검사한다. 세션마다 독립 상태를 가지며 지속 저장하지 않는다.
export type Point = {x: number, y: number}
export type Case = {id: string, origin: Point?, move: Point, record: Point?, evidence: string, verdict: string}
export type Snapshot = {
    phase: string, token: string, asked: {[string]: boolean}, selected: string?, feedback: string?,
    origin: Point?, move: Point?, record: Point?, verdict: string?, completed: number, label: boolean,
}
export type Session = {snapshot: () -> Snapshot, apply: (string, string, string) -> string?}
local MissionService = {}
local QUESTIONS = {origin = true, move = true, record = true}
local EVIDENCE = {match = true, mismatch = true, missing = true}
local VERDICTS = {approve = true, verify = true, reject = true}
local function copyPoint(point: Point?): Point?
    return if point then {x = point.x, y = point.y} else nil
end
function MissionService.new(pack: {Case}, reverse: boolean): Session
    assert(#pack == 3, "inspection pack needs three cases")
    -- 자료 표는 함수가 아닌 서버 데이터다. Q3의 직접 호출 규칙을 유지한다 (DEC-17).
    local cases = {pack[1], pack[2], pack[3]}
    local order = {1, 2, 3}
    if reverse then order[2] = 3; order[3] = 2 end
    local index = 1
    local token = 0
    local phase = "ready"
    local asked: {[string]: boolean} = {}
    local selected: string? = nil
    local feedback: string? = nil
    local completed = 0
    local label = false
    local function snapshot(): Snapshot
        local case = cases[order[index]]
        return {
            phase = phase, token = tostring(token), asked = table.clone(asked), selected = selected,
            feedback = feedback, completed = completed, label = label,
            origin = if asked.origin then copyPoint(case.origin) else nil,
            move = if asked.move then copyPoint(case.move) else nil,
            record = if asked.record then copyPoint(case.record) else nil,
            verdict = if phase == "resolved" or phase == "rest" then case.verdict else nil,
        }
    end
    local function begin()
        token += 1
        phase = "review"
        table.clear(asked)
        selected = nil
        feedback = nil
    end
    -- nil은 무시한 입력. 완료와 다음 선택은 실제 상태 전환에서만 센다.
    local function apply(action: string, detail: string, turn: string): string?
        if action == "sync" then return "sync" end
        if turn ~= tostring(token) then return nil end
        if action == "start" and phase == "ready" then
            begin()
            return "case_started"
        end
        if action == "next" and phase == "resolved" then
            index += 1
            if index > #order then
                index = 1
                local first = table.remove(order, 1) :: number
                table.insert(order, first) -- 재참여에서는 사건 순서를 순환한다.
            end
            begin()
            return "next_chosen"
        end
        if action == "rest" and phase == "resolved" then
            phase = "rest"
            return "rest_chosen"
        end
        if action == "resume" and phase == "rest" then
            phase = "resolved"
            return "resumed"
        end
        if phase ~= "review" then return nil end
        local case = cases[order[index]]
        if action == "ask" and QUESTIONS[detail] then
            feedback = nil
            if asked[detail] then return "replayed" end
            asked[detail] = true
            return "question_opened"
        end
        if action == "evidence" and EVIDENCE[detail] then
            if not (asked.origin and asked.move and asked.record) then
                feedback = "need_questions"
                return "decision_retry"
            end
            if selected == detail then return nil end
            selected = detail
            feedback = nil
            return "evidence_selected"
        end
        if action == "decide" and VERDICTS[detail] then
            if not (asked.origin and asked.move and asked.record) then
                feedback = "need_questions"
            elseif selected == nil then
                feedback = "need_evidence"
            elseif selected ~= case.evidence or detail ~= case.verdict then
                feedback = if case.evidence == "missing" then "check_missing"
                    elseif case.evidence == "mismatch" then "check_record" else "check_origin"
                selected = nil
            else
                phase = "resolved"
                feedback = case.evidence
                completed += 1
                label = true -- 행동과 결과 뒤에만 새 용어를 붙인다 (INV-15).
                return "result_shown"
            end
            return "decision_retry"
        end
        return nil
    end
    return {snapshot = snapshot, apply = apply}
end
return MissionService
