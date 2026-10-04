"""수학 대사 검사 E1·E2 (K3 §3 · INV-7) — 모델 없이 정확한 유리수 계산으로만 판정한다.

명제(content/math_claims.yaml) 종류:
  coordinate     기준점에서 방향별로 움직인 결과 칸이 states 와 같은가        조건: origin · axes
  slope          rise ÷ run 이 states 와 같은가                            조건: run_nonzero · same_unit
  slope_compare  두 기울기의 관계(steeper·less_steep·equal)가 맞는가        조건: run_nonzero · same_unit
  line_point     점이 직선 y = m·x + b 위에 있는지(states: true/false)       조건: domain

대사와의 연결: 명제가 말하는 값(이동·결과 칸·기울기 값·점)이 원문(Source)에 그대로 있는지 본다.
낱말은 잠긴 Q2 용어집에서 읽는다 — 검사기에 특정 언어의 말을 적지 않는다. 번역문은 i18n.do_not_translate 가 맡는다.
"""
from __future__ import annotations

import re
from fractions import Fraction

DIRECTIONS = {"right": (1, 0), "left": (-1, 0), "up": (0, 1), "down": (0, -1)}
REQUIRED = {"coordinate": ("origin", "axes"), "slope": ("run_nonzero", "same_unit"), "slope_compare": ("run_nonzero", "same_unit"),
            "line_point": ("domain",)}
AXES = "x_right_y_up"   # 정본 값 cv.coordinate_expression: 세로 신호판, 오른쪽·위가 양수
DOMAINS = ("real", "grid_integer")
NEAR = r"\s*[^\d\n]{0,4}\s*"   # 낱말과 수 사이에 올 수 있는 짧은 사이(조사·공백 등)
MATH_SHAPE = r"\d\s*[+\-×÷*=<>]\s*\d|\(\s*-?\d+\s*,\s*-?\d+\s*\)"   # 식 모양 — 수끼리 셈하거나 좌표꼴이면 수학 대사로 본다
FRACTION = r"\d\s*/\s*\d"   # 분수 꼴. 진행 표시('신호 2/3')와 섞이므로 수학 용어가 함께 있을 때만 수학 대사로 본다


class ClaimError(ValueError):
    pass


def _num(value) -> Fraction:
    """정확한 유리수만 받는다 — 정수, 또는 '분자/분모'·소수를 적은 글자.

    실수(float)는 2진 근삿값이라 받지 않는다. 글자로 적은 소수('0.5')는 정확히 1/2 로 읽히므로 받는다.
    """
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ClaimError(f"수는 정수, 또는 '분자/분모'·소수를 적은 글자여야 한다 — 실수는 근삿값이라 받지 않는다 ({value!r})")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ClaimError(f"수로 읽을 수 없다 ({value!r})") from exc


def _point(value) -> tuple[Fraction, Fraction]:
    if not (isinstance(value, list) and len(value) == 2):
        raise ClaimError(f"점은 [x, y] 여야 한다 ({value!r})")
    return _num(value[0]), _num(value[1])


def _slope(part: dict) -> Fraction:
    run = _num(part.get("run"))
    if run == 0:
        raise ClaimError("가로 변화(run)가 0 — 기울기가 정의되지 않는다")
    return _num(part.get("rise")) / run


def evaluate(claim: dict) -> bool:
    """명제가 참인지. 형식이 틀리거나 계산할 수 없으면 ClaimError."""
    kind = claim.get("kind") if isinstance(claim, dict) else None
    if kind == "coordinate":
        x, y = _point(claim.get("origin"))
        for move in claim.get("moves") or []:
            dx, dy = DIRECTIONS.get(move.get("dir"), (None, None)) if isinstance(move, dict) else (None, None)
            if dx is None:
                raise ClaimError(f"방향 {move.get('dir') if isinstance(move, dict) else move!r} 를 모른다")
            n = _num(move.get("n"))
            x, y = x + dx * n, y + dy * n
        return (x, y) == _point(claim.get("states"))
    if kind == "slope":
        return _slope(claim) == _num(claim.get("states"))
    if kind == "slope_compare":
        a, b = _slope(claim.get("this") or {}), _slope(claim.get("other") or {})
        if claim.get("states") not in ("steeper", "less_steep", "equal"):
            raise ClaimError(f"관계 {claim.get('states')!r} 를 모른다")
        actual = "steeper" if abs(a) > abs(b) else "less_steep" if abs(a) < abs(b) else "equal"
        return actual == claim.get("states")
    if kind == "line_point":
        line = claim.get("line") or {}
        x, y = _point(claim.get("point"))
        if not isinstance(claim.get("states"), bool):
            raise ClaimError("line_point 의 states 는 true/false")
        return (y == _num(line.get("m")) * x + _num(line.get("b"))) == claim["states"]
    raise ClaimError(f"명제 종류 {kind!r} 를 모른다")


def _number_re(value: Fraction) -> str | None:
    """수를 글자에서 찾는 정규식 — 앞뒤로 숫자·소수점·분수 기호가 붙지 않아야 한다(2 가 2/3·2.5 에 걸리지 않게)."""
    if value.denominator != 1:
        return None   # 분수 표기는 언어마다 달라 대사와 묶지 않는다
    return rf"(?<![\d./]){re.escape(str(value.numerator))}(?![\d./])"


def _word(rules, key: str) -> str | None:
    text = rules.glossary.get("strings", {}).get(key)
    return text if isinstance(text, str) and text.strip() else None


def _direction_words(rules) -> dict[str, str]:
    """방향 → 잠긴 Q2 용어집의 일상 표현(expr.position.<방향>)."""
    out = {}
    for goal in rules.world_spec.get("language_goals", []):
        for key in goal.get("everyday_expression_keys", []):
            name = key.rsplit(".", 1)[-1]
            if name in DIRECTIONS and _word(rules, key):
                out[name] = _word(rules, key)
    return out


def _line_expression(m: int, b: int) -> tuple[str, str]:
    """정수 계수 직선식은 식 전체가 대사에 있어야 한다 — `y = 2x + 1` (사람 결정 Q3-SHAPE-RULES).

    숫자가 따로따로 나오는지만 보면 계수를 바꿔 적은 대사(`y = 1x + 2`)가 통과한다 (리뷰 R-Q3 32차).
    """
    coeff = {1: "", -1: "-"}.get(m, str(m))
    if b:
        shown = f"y = {coeff}x {'+' if b > 0 else '-'} {abs(b)}"
        pattern = rf"y\s*=\s*{re.escape(coeff)}\s*x\s*{'\\+' if b > 0 else '-'}\s*{abs(b)}(?![\d.])"
    else:
        shown = f"y = {coeff}x"
        pattern = rf"y\s*=\s*{re.escape(coeff)}\s*x(?!\s*[+\-]\s*\d)"
    return shown, pattern


def stated_patterns(claim: dict, rules) -> list[tuple[str, str]]:
    """원문에 그대로 있어야 하는 것 — (설명, 정규식).

    수로 묶을 수 없는 값(비교 방향·분수)은 명제가 states_text 로 '대사에 있어야 할 말'을 적어야 한다.
    그 말은 데이터(명제 파일)에 두고 검사기에는 특정 언어의 말을 적지 않는다.
    """
    kind, out = claim.get("kind"), []
    stated = claim.get("states_text")
    if isinstance(stated, str) and stated.strip():
        out.append((stated, re.escape(stated)))
    if kind == "coordinate":
        words = _direction_words(rules)
        for move in claim.get("moves") or []:
            word, n = words.get(move.get("dir")), _number_re(_num(move.get("n")))
            if word and n:
                out.append((f"{word} {move.get('n')}", re.escape(word) + NEAR + n))
        x, y = _point(claim.get("states"))
        if x.denominator == y.denominator == 1:
            out.append((f"({x}, {y})", rf"\(\s*{x.numerator}\s*,\s*{y.numerator}\s*\)"))
    elif kind == "slope":
        label, value = _word(rules, "term.slope.name"), _number_re(_num(claim.get("states")))
        if label:
            out.append((label, re.escape(label)))
        if value:
            out.append((str(claim.get("states")), value))
    elif kind == "line_point":
        x, y = _point(claim.get("point"))
        if x.denominator == y.denominator == 1:
            out.append((f"({x}, {y})", rf"\(\s*{x.numerator}\s*,\s*{y.numerator}\s*\)"))
        line = claim.get("line") or {}
        m, b = _num(line.get("m")), _num(line.get("b"))
        if m.denominator == b.denominator == 1:
            out.append(_line_expression(int(m), int(b)))
        if any(_num(line.get(n)).denominator != 1 for n in ("m", "b")):
            stated = claim.get("line_text")
            if isinstance(stated, str) and stated.strip():
                out.append((stated, re.escape(stated)))
    return out


def _math_terms(rules) -> list[str]:
    return [t for goal in rules.world_spec.get("language_goals", []) for t in [_word(rules, goal.get("label_key", ""))] if t]


def needs_states_text(claim: dict) -> bool:
    """수만으로는 대사와 묶을 수 없는 명제 — 비교 방향, 또는 분수·소수로 적은 값."""
    kind = claim.get("kind")
    if kind == "slope_compare":
        return True
    if kind == "slope":
        try:
            return _num(claim.get("states")).denominator != 1
        except ClaimError:
            return False
    if kind == "line_point":
        return True   # 위에 있다·없다는 말로 표현되므로 수만으로 묶을 수 없다
    if kind == "coordinate":
        try:
            moves = [_num(m.get("n")) for m in (claim.get("moves") or []) if isinstance(m, dict)]
            if any(v.denominator != 1 for v in moves):
                return True
            values = list(_point(claim.get("states")))
            return any(v.denominator != 1 for v in values)
        except ClaimError:
            return False
    return False


def _fractional_line(claim: dict) -> bool:
    if claim.get("kind") != "line_point":
        return False
    line = claim.get("line") or {}
    try:
        return any(_num(line.get(n)).denominator != 1 for n in ("m", "b"))
    except ClaimError:
        return False


def _said(value) -> bool:
    """대사에 있어야 할 말로 쓸 수 있는가 — 비어 있지 않은 글자여야 한다(수를 적으면 묶이지 않는다)."""
    return isinstance(value, str) and bool(value.strip())


def truth(tree, rules, config) -> list[str]:
    """E1 — 수학 대사의 명제가 실제로 맞고, 대사가 그 명제를 말한다. 수학이 든 대사는 모두 명제를 가진다."""
    if not tree.claims:
        return ["수학 명제(content/math_claims.yaml)가 없다"]
    out, tied = [], set()
    for claim in tree.claims:
        cid = claim.get("id", "?") if isinstance(claim, dict) else "?"
        try:
            if not evaluate(claim):
                out.append(f"{cid}: 명제가 거짓이다 (E1) — 문구 {claim.get('line_key') if isinstance(claim, dict) else '?'}")
        except (ClaimError, AttributeError, TypeError) as exc:
            out.append(f"{cid}: 판정할 수 없다 — {exc}")
            continue
        row = tree.strings.get(claim.get("line_key"))
        if row is None:
            out.append(f"{cid}: 명제가 가리키는 문구 키 {claim.get('line_key')} 가 LocalizationTable 에 없다")
            continue
        tied.add(claim.get("line_key"))
        source = row.get("Source", "")
        if needs_states_text(claim) and not _said(claim.get("states_text")):
            out.append(f"{cid}: 수만으로는 대사와 묶을 수 없는 명제다 — states_text 에 대사가 반드시 말해야 할 말을 글자로 적어야 한다 (E1)")
        if _fractional_line(claim) and not _said(claim.get("line_text")):
            out.append(f"{cid}: 분수 계수는 수로 대사와 묶을 수 없다 — line_text 에 대사가 말하는 식을 글자로 적어야 한다 (E1)")
        out += [f"{cid}: 대사 {claim.get('line_key')} 가 명제의 '{shown}' 을 말하지 않는다 — 명제와 대사가 따로 논다"
                for shown, pattern in stated_patterns(claim, rules) if not re.search(pattern, source)]
    terms = _math_terms(rules)
    for key, row in sorted(tree.strings.items()):
        source = row.get("Source", "")
        has_term = any(t in source for t in terms)
        if has_term and source.strip() in terms:
            continue   # 용어의 이름 자체다 — 대사가 아니므로 명제를 요구하지 않는다
        has_math = (bool(_fragments(source, rules)) or has_term or bool(re.search(MATH_SHAPE, source))
                    or (bool(re.search(FRACTION, source)) and has_term))
        if has_math and key not in tied:
            out.append(f"{key}: 수학이 든 대사인데 명제가 없다 — content/math_claims.yaml 에 적어야 검사할 수 있다 (E1)")
    return out


def _fragments(text: str, rules) -> list[str]:
    return [m.group() for r in rules.world_spec.get("do_not_translate", []) for m in re.finditer(r["pattern"], text)]


def conditions(tree, rules, config) -> list[str]:
    """E2 — 정의역·단위·예외·그림 조건이 빠지지 않았고, 적어 둔 조건이 명제의 값과 맞는가."""
    out = []
    for claim in tree.claims:
        if not isinstance(claim, dict):
            out.append("명제는 객체여야 한다")
            continue
        cid, kind, raw = claim.get("id", "?"), claim.get("kind"), claim.get("conditions")
        if raw is not None and not isinstance(raw, dict):
            out.append(f"{cid}: 조건(conditions)은 '이름: 값' 표여야 한다 — {raw!r} 로는 명제와 대조할 수 없다 (E2)")
            continue
        cond = raw or {}
        if kind not in REQUIRED:
            out.append(f"{cid}: 명제 종류 {kind!r} 를 모른다")
        out += [f"{cid}: 조건 {c} 가 빠졌다 (E2)" for c in REQUIRED.get(kind, ()) if c not in cond]
        try:
            out += _condition_values(cid, kind, cond, claim)
        except ClaimError as exc:
            out.append(f"{cid}: 조건을 값으로 대조할 수 없다 — {exc}")
    return out


def _condition_values(cid: str, kind: str, cond: dict, claim: dict) -> list[str]:
    out = []
    if "origin" in cond and _point(cond["origin"]) != _point(claim.get("origin")):
        out.append(f"{cid}: 조건의 기준점 {cond['origin']} 이 명제의 기준점 {claim.get('origin')} 과 다르다")
    if "axes" in cond and cond["axes"] != AXES:
        out.append(f"{cid}: 축 방향은 {AXES} 이어야 한다 (정본 값 cv.coordinate_expression)")
    if "run_nonzero" in cond:
        parts = [claim] if kind == "slope" else [claim.get("this") or {}, claim.get("other") or {}]
        if cond["run_nonzero"] is not True or any(_num(p.get("run")) == 0 for p in parts):
            out.append(f"{cid}: 가로 변화가 0 이 아니라는 조건이 성립하지 않는다 (E2 예외 조건)")
    if "same_unit" in cond and cond["same_unit"] != "grid_cell":
        out.append(f"{cid}: 높이·가로 변화의 단위가 같은 격자 칸(grid_cell)이 아니다")
    if "domain" in cond:
        if cond["domain"] not in DOMAINS:
            out.append(f"{cid}: 정의역 {cond['domain']!r} 을 모른다")
        elif cond["domain"] == "grid_integer":
            line = claim.get("line") or {}
            values = list(_point(claim.get("point"))) + [_num(line.get("m")), _num(line.get("b"))]
            if any(v.denominator != 1 for v in values):
                out.append(f"{cid}: 정의역이 격자 정수인데 정수가 아닌 값이 있다 (E2)")
    return out
