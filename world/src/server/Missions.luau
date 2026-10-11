--!strict
-- 첫 사건 팩. 정답과 근거 조건은 서버에만 둔다.
return {
    {id = "parcel_a", origin = {x = 0, y = 0}, move = {x = 2, y = 1}, record = {x = 2, y = 1}, evidence = "match", verdict = "approve"},
    {id = "parcel_b", origin = {x = 0, y = 0}, move = {x = 2, y = 1}, record = {x = 1, y = 2}, evidence = "mismatch", verdict = "reject"},
    {id = "parcel_c", origin = nil, move = {x = 2, y = 1}, record = nil, evidence = "missing", verdict = "verify"},
}
