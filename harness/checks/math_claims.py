"""수학 대사 검사 E1·E2 (K3 §3 · INV-7) — 모델 없이 정확한 유리수 계산으로만 판정한다.

명제(content/math_claims.yaml) 종류:
  coordinate  기준점에서 방향별로 움직인 결과 칸이 states 와 같은가        조건: origin · axes
  slope       rise ÷ run 이 states 와 같은가                            조건: run_nonzero · same_unit
  slope_compare  두 기울기의 관계(steeper·less_steep·equal)가 맞는가     조건: run_nonzero · same_unit
  line_point  점이 직선 y = m·x + b 위에 있는지(states: true/false)        조건: domain
"""
from __future__ import annotations

from fractions import Fraction

DIRECTIONS = {"right": (1, 0), "left": (-1, 0), "up": (0, 1), "down": (0, -1)}
REQUIRED = {"coordinate": ("origin", "axes"), "slope": ("run_nonzero", "same_unit"), "slope_compare": ("run_nonzero", "same_unit"),
            "line_point": ("domain",)}
AXES = "x_right_y_up"   # 정본 값 cv.coordinate_expression: 세로 신호판, 오른쪽·위가 양수


class ClaimError(ValueError):
    pass


def _num(value) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ClaimError(f"수는 정수나 '분자/분모' 글자여야 한다 ({value!r})")
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
    kind = claim.get("kind")
    if kind == "coordinate":
        x, y = _point(claim.get("origin"))
        for move in claim.get("moves") or []:
            dx, dy = DIRECTIONS.get(move.get("dir"), (None, None))
            if dx is None:
                raise ClaimError(f"방향 {move.get('dir')!r} 를 모른다")
            n = _num(move.get("n"))
            x, y = x + dx * n, y + dy * n
        return (x, y) == _point(claim.get("states"))
    if kind == "slope":
        return _slope(claim) == _num(claim.get("states"))
    if kind == "slope_compare":
        a, b = _slope(claim.get("this") or {}), _slope(claim.get("other") or {})
        actual = "steeper" if abs(a) > abs(b) else "less_steep" if abs(a) < abs(b) else "equal"
        if claim.get("states") not in ("steeper", "less_steep", "equal"):
            raise ClaimError(f"관계 {claim.get('states')!r} 를 모른다")
        return actual == claim.get("states")
    if kind == "line_point":
        line = claim.get("line") or {}
        x, y = _point(claim.get("point"))
        if not isinstance(claim.get("states"), bool):
            raise ClaimError("line_point 의 states 는 true/false")
        return (y == _num(line.get("m")) * x + _num(line.get("b"))) == claim["states"]
    raise ClaimError(f"명제 종류 {kind!r} 를 모른다")


def truth(tree, rules, config) -> list[str]:
    """E1 — 수학 대사의 명제가 실제로 맞는가."""
    if not tree.claims:
        return ["수학 명제(content/math_claims.yaml)가 없다"]
    out = []
    for claim in tree.claims:
        cid = claim.get("id", "?") if isinstance(claim, dict) else "?"
        try:
            if not evaluate(claim):
                out.append(f"{cid}: 명제가 거짓이다 (E1) — 문구 {claim.get('line_key')}")
        except (ClaimError, AttributeError, TypeError) as exc:
            out.append(f"{cid}: 판정할 수 없다 — {exc}")
        if not isinstance(claim, dict):
            continue
        row = tree.strings.get(claim.get("line_key"))
        if row is None:
            out.append(f"{cid}: 명제가 가리키는 문구 키 {claim.get('line_key')} 가 LocalizationTable 에 없다")
            continue
        shown = stated_text(claim)
        if shown is not None and _squash(shown) not in _squash(row.get("Source", "")):
            out.append(f"{cid}: 대사 {claim.get('line_key')} 가 명제의 값 '{shown}' 을 말하지 않는다 — 명제와 대사가 따로 논다")
    return out


def _squash(text: str) -> str:
    return "".join(str(text).split())


def stated_text(claim: dict) -> str | None:
    """대사에 그대로 나와야 하는 명제의 값(좌표·기울기 수·점). 관계(slope_compare)는 말로 나와서 None."""
    kind, states = claim.get("kind"), claim.get("states")
    if kind == "coordinate" and isinstance(states, list) and len(states) == 2:
        return f"({states[0]}, {states[1]})"
    if kind == "slope" and isinstance(states, (int, str)) and not isinstance(states, bool):
        return f"기울기는 {states}"
    if kind == "line_point" and isinstance(claim.get("point"), list) and len(claim["point"]) == 2:
        return f"({claim['point'][0]}, {claim['point'][1]})"
    return None


def conditions(tree, rules, config) -> list[str]:
    """E2 — 정의역·단위·예외·그림 조건이 빠지지 않았는가. 종류마다 필요한 조건이 있고 실제 값과 맞아야 한다."""
    out = []
    for claim in tree.claims:
        if not isinstance(claim, dict):
            out.append("명제는 객체여야 한다")
            continue
        cid, kind, cond = claim.get("id", "?"), claim.get("kind"), claim.get("conditions") or {}
        missing = [c for c in REQUIRED.get(kind, ()) if c not in cond]
        if kind not in REQUIRED:
            out.append(f"{cid}: 명제 종류 {kind!r} 를 모른다")
        out += [f"{cid}: 조건 {c} 가 빠졌다 (E2)" for c in missing]
        if "origin" in cond and cond["origin"] != claim.get("origin"):
            out.append(f"{cid}: 조건의 기준점 {cond['origin']} 이 명제의 기준점과 다르다")
        if "axes" in cond and cond["axes"] != AXES:
            out.append(f"{cid}: 축 방향은 {AXES} 이어야 한다 (정본 값 cv.coordinate_expression)")
        if cond.get("run_nonzero") is not None:
            parts = [claim] if kind == "slope" else [claim.get("this") or {}, claim.get("other") or {}]
            zero = [p for p in parts if p.get("run") in (0, "0")]
            if cond["run_nonzero"] is not True or zero:
                out.append(f"{cid}: 가로 변화가 0 이 아니라는 조건이 성립하지 않는다 (E2 예외 조건)")
        if "same_unit" in cond and cond["same_unit"] != "grid_cell":
            out.append(f"{cid}: 높이·가로 변화의 단위가 같은 격자 칸(grid_cell)이 아니다")
        if "domain" in cond and cond["domain"] not in ("real", "grid_integer"):
            out.append(f"{cid}: 정의역 {cond['domain']!r} 을 모른다")
    return out
