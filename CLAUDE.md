# rb — Roblox Studio × Claude Code

## 세션 시작 시
1. `intent.md` 를 먼저 읽는다. 목표·제품 순서(Q1~Q8)·불변식·결정 항목(DEC)의 정본이다. 결정·검토 상태는 `decisions.md` 에 있다(사람이 대화에서 명시적으로 답한 것만 적는다). 작업 방식은 masterwork(Intent → Diagram → 작업 Graph → Harness → Evidence)다.
   원천 자료 색인은 `docs/knowledge/K0-docs-index.md`.
2. `docs/02-start-here.md` 에서 연결 환경과 Studio 연결 절차를 확인한다.
3. 이 세션에 Roblox Studio MCP 도구(`script_read`, `search_game_tree` 등)가 보이는지 확인한다. 안 보이면 start-here §3 의 0단계부터 진행한다.

## 구조·순서 경고
- `⚠️ 구조·순서 경고` 나 `[W1]`~`[W7]` 확인 창이 뜨면 넘기지 말고 원인부터 해소한다. 규칙은 `intent.md` §9, 장치는 `tools/flow_guard.py`(훅: `.claude/settings.json`)다.
- 장치나 Intent 형식을 고치면 `python3 -m unittest discover -s tools` 를 다시 돌린다.
- `[W8]` 이 뜨면 `intent.md` §11 의 해당 방향(전방·후방·위·아래·좌·우)을 점검하고 결과를 `evidence.jsonl` 에 `kind: vector_review` 로 추가한다(관찰·제안·다음 할 일·출처). 세부 근거는 `docs/knowledge/K6-six-vectors.md`.

## 단계 검증 — 3층 게이트 (근거 원장 D-VERIFY)
- ① 바뀔 때마다 자동 검사: `python3 -m unittest discover -s tools` · `python3 -m unittest discover -s tests` · `python3 tools/validate_spec.py`. 단계 기준 검사와 기록은 `python3 tools/verify.py run <Q>`.
- ② 단계를 잠그기 전에만 독립 리뷰: `python3 tools/verify.py review <Q>` (Codex, 오래 걸리면 백그라운드). 리뷰 중에는 그 단계 산출물을 고치지 않는다.
- ③ 사람이 대화에서 잠금을 승인한 뒤에만 `verify.py approve <Q> --source "<사람의 말·날짜>"` → `verify.py lock <Q>`. 남은 조건은 `verify.py gate <Q>`.
- 산출물·계약이 바뀌면 이전 검증 기록은 낡는다 — run·review 를 다시 돌린다. 원본 출력은 `outputs/verify/<Q>/`.

## 작업 원칙 (원 가이드 `docs/01-roblox-studio-mcp-guide.md` §권장 운영 방식)
- 처음엔 읽기 전용이다. 수정은 사람이 범위를 정한 뒤에 한다.
- 수정은 한 요청에 한 기능만 한다. 끝나면 바뀐 Instance 경로, diff 요약, Play 테스트 결과를 보고한다.
- 월드 생성·대규모 리팩터링·GUI 개편 같은 큰 변경은 스테이징 Place 에서만 한다.
- 운영 Place 의 대량 삭제·권한·DataStore 구조·결제/보상 경제 변경은 사람이 결정한다.
- 변경 전에 Git 커밋이나 Place 버전으로 되돌릴 지점을 남긴다.
- 이 저장소는 공개(PUBLIC)다. 로컬 경로·계정 정보·비밀값을 커밋하지 않는다.
