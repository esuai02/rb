--!strict
-- 같은 서버 규칙을 실제 Luau로 검사한다. 세션마다 독립 상태를 가지며 지속 저장하지 않는다.
export type Point = {x: number, y: number}
export type Case = {
    id: string, theme: string?, stage: string?, origin: Point?, move: Point?, line: number?, record: Point?,
    evidence: string, verdict: string,
}
-- 사건마다 서버가 남기는 관찰. 점수로 바꾸지 않는다.
-- first: 첫 유효 선택(근거+도장)이 맞았는지 · help: 그 선택 전에 그림 도움을 봤는지 · opened: 이 사건에서 도움을 열었는지
export type Record = {
    id: string, theme: string, stage: string, first: string?, help: boolean, opened: boolean,
    retries: number, completed: boolean,
}
export type Snapshot = {
    phase: string, token: string, asked: {[string]: boolean}, selected: string?, feedback: string?,
    case: string, theme: string, stage: string, index: number, total: number, help: boolean,
    origin: Point?, move: Point?, line: number?, record: Point?, verdict: string?, completed: number, label: boolean,
    summary: {Record}?,
}
export type Session = {snapshot: () -> Snapshot, apply: (string, string, string) -> string?}
local MissionService = {}
local QUESTIONS = {origin = true, move = true, record = true}
local EVIDENCE = {match = true, mismatch = true, missing = true}
local VERDICTS = {approve = true, verify = true, reject = true}
local function copyPoint(point: Point?): Point?
    return if point then {x = point.x, y = point.y} else nil
end
local MAX_CASES = 6
local function newRecord(case: Case): Record
    return {
        id = case.id, theme = case.theme or "coordinate", stage = case.stage or "first",
        first = nil, help = false, opened = false, retries = 0, completed = false,
    }
end
function MissionService.new(pack: {Case}): Session
    assert(#pack >= 1 and #pack <= MAX_CASES, "inspection pack needs 1 to 6 cases")
    -- 자료 표는 함수가 아닌 서버 데이터다. Q3의 직접 호출 규칙을 유지한다 (DEC-17).
    -- 글자 그대로 만든 표라야 번호로 읽어도 검사할 수 있다. 3사건 팩은 뒤쪽이 nil 이라 #cases 가 3이다.
    local cases: {Case} = {pack[1], pack[2], pack[3], pack[4], pack[5], pack[6]}
    local total = #cases
    local index = 1
    local token = 0 -- 다시 시작해도 줄지 않는다. 이전 화면에서 온 입력은 계속 거절된다.
    local phase = "ready"
    local asked: {[string]: boolean} = {}
    local selected: string? = nil
    local feedback: string? = nil
    local help = false
    local completed = 0
    local label = false
    -- 기록 표는 한 번만 만들고, 다시 시작할 때는 같은 표를 비우고 다시 채운다.
    local records: {Record} = {}
    local function fillRecords()
        table.clear(records)
        for _, case in cases do table.insert(records, newRecord(case)) end
    end
    fillRecords()
    local function snapshot(): Snapshot
        local case = cases[index]
        local summary: {Record}? = nil
        if phase == "finished" then
            local copies: {Record} = {}
            for i, record in records do copies[i] = table.clone(record) end
            summary = copies
        end
        return {
            phase = phase, token = tostring(token), asked = table.clone(asked), selected = selected,
            feedback = feedback, completed = completed, label = label, help = help,
            case = case.id, theme = case.theme or "coordinate", stage = case.stage or "first",
            index = index, total = total,
            origin = if asked.origin then copyPoint(case.origin) else nil,
            move = if asked.move then copyPoint(case.move) else nil,
            line = if asked.move then case.line else nil,
            record = if asked.record then copyPoint(case.record) else nil,
            verdict = if phase == "resolved" or phase == "rest" then case.verdict else nil,
            summary = summary,
        }
    end
    local function clearCase()
        table.clear(asked)
        selected = nil
        feedback = nil
        help = false
    end
    local function begin()
        token += 1
        phase = "review"
        clearCase()
    end
    local function allAsked(): boolean
        return asked.origin == true and asked.move == true and asked.record == true
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
            if index >= #cases then
                token += 1
                phase = "finished" -- 유한한 순회의 끝. 기록만 보여 주고 더 진행하지 않는다.
                clearCase()
                return "tour_finished"
            end
            index += 1
            begin()
            return "next_chosen"
        end
        if action == "restart" and phase == "finished" then
            token += 1 -- 다음 참여자: 기록·완료 수를 비우고 토큰은 계속 올린다.
            index = 1
            phase = "ready"
            clearCase()
            completed = 0
            label = false
            fillRecords()
            return "restarted"
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
        local case = cases[index]
        local record = records[index]
        if action == "ask" and QUESTIONS[detail] then
            feedback = nil
            if asked[detail] then return "replayed" end
            asked[detail] = true
            return "question_opened"
        end
        -- 계산한 결과를 보여 주는 그림은 선택 도움이다. 처음/새 장면 모두 같은 규칙으로 연다.
        if action == "help" and detail == "none" then
            if help or not allAsked() then return nil end
            help = true
            record.opened = true
            return "help_opened"
        end
        if action == "evidence" and EVIDENCE[detail] then
            if not allAsked() then
                feedback = "need_questions"
                return "decision_retry"
            end
            if selected == detail then return nil end
            selected = detail
            feedback = nil
            return "evidence_selected"
        end
        if action == "decide" and VERDICTS[detail] then
            if not allAsked() then
                feedback = "need_questions"
                return "decision_retry"
            end
            if selected == nil then
                feedback = "need_evidence"
                return "decision_retry"
            end
            local chosen = selected :: string
            local correct = chosen == case.evidence and detail == case.verdict
            if record.first == nil then -- 다시 골라 해결해도 첫 선택 기록은 바뀌지 않는다.
                record.first = if correct then "correct" else "incorrect"
                record.help = help
            end
            if not correct then
                record.retries += 1
                -- 안내는 기대 근거가 아니라 학생이 고른 근거에서 출발한다. 결과 전에는 판정 조건을 보내지 않는다.
                feedback = if chosen == "match" then "check_match" elseif chosen == "mismatch" then "check_mismatch" else "check_missing"
                selected = nil
                return "decision_retry"
            end
            phase = "resolved"
            feedback = nil
            completed += 1
            record.completed = true
            label = true -- 행동과 결과 뒤에만 새 용어를 붙인다 (INV-15).
            return "result_shown"
        end
        return nil
    end
    return {snapshot = snapshot, apply = apply}
end
return MissionService
