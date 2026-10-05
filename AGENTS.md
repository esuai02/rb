# rb 작업 재개

- `intent.md` r4·`decisions.md`·`graph.json`을 먼저 읽는다. 기존 ID·단계 순서·사람 결정·DEC-18 고정 범위를 보존한다.
- main만 보지 말고 현재 작업 브랜치를 확인한다. 이번 출발점은 `feat/q2-world-graph@59f56e8`, Q1~Q3 LOCKED / Q4 FOCUS다.
- 설치된 기존 Masterwork를 `MASTERWORK_HELPER`로 연결하고 `python3 tools/check.py` → `python3 tools/verify.py next`로 상태를 복원한다.
- 검증은 기존 `harness/`·`tests/`·원장을 쓴다. UI·서버·번역·분석·장식을 맥락마다 복사하지 않고 기존 모듈/정본 설정을 확장한다.
- 한 번에 현재 Q4의 관찰된 격차 하나. 파일/원장은 한 작성자, 독립 리뷰 중 해당 파일 변경 금지. 새 리뷰 상한·고정 범위는 기존 Intent를 따른다.
- 코드·명세 검사 PASS를 Studio·실제 기기·2인·학생 재미 PASS로 바꾸지 않는다. 새 기록은 원본 출력과 해시를 보존한다.
- 사람이 실제 말한 결정만 기록하고 기존 결정은 다시 묻지 않는다. 잠금은 검토한 현재 버전의 실제 승인으로만 한다.
