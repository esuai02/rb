critical | harness/checks/server.py:32-44,476-490 | 보상 도달 경로를 직접 보상 함수만 따라가 간접 헬퍼를 놓친다 | `handler → finish() → MissionService.openGate() → RewardService.grant()` 구조에서 verdict 없이 보상해도 `reward_after_verdict` 결과가 빈 목록 | 보상 도달 함수의 전이 폐포를 계산하거나 미해석 호출을 실패 처리

critical | harness/checks/server.py:125-150,359-388 | 변수로 만든 `RemoteEvent[eventName]:Connect(...)`를 원격 처리로 인식하지 않는다 | `eventName = "OnServerEvent"`인 동적 대괄호 등록은 `remote_validation`·`remote_cooldown` 모두 빈 결과 | 상수 해석을 확장하고 미해석 원격 멤버 등록은 보수적으로 실패 처리

major | harness/checks/analytics.py:64-87 | 분석 전송 함수의 2단계 별칭을 검사하지 않는다 | `send = Analytics.log; send2 = send; send2(player, ...)`가 허용 이벤트·필드 검사를 우회하고 결과가 빈 목록 | 별칭 해석을 끝까지 따라가거나 미해석 함수 호출을 거부

major | harness/checks/i18n.py:33-45, harness/luau.py:119-135 | 변수로 선택한 문구 함수 호출을 놓쳐 끊긴 키가 통과한다 | `method = "get"; Text[method]("goal.missing")`에서 `i18n.missing_key`가 빈 결과 | 상수 인덱스를 해석하고 동적 문구 함수 호출은 검사 불가로 실패 처리

major | harness/checks/math_claims.py:104-137,166-188 | `line_point`의 참·거짓 결과가 대사에 표현됐는지 검사하지 않는다 | `states: false`인 `(2,4), y=2x+1` 명제가 “위에 있어”라고 말해도 점·식만 일치하면 통과 | boolean 명제에도 데이터의 `states_text`를 요구하고 원문 존재를 검사

major | harness/source.py:130-149 | 같은 최상위 서비스 안에서 동일 파일을 두 위치에 매핑해도 중복 매핑으로 거부하지 않는다 | 중복 판단이 `owners[path] != chain[0]`만 비교하므로 두 매핑의 `chain[0]`이 같으면 통과 | 전체 매핑 경로를 저장·비교해 최상위 서비스가 같아도 중복 거부

major | harness/checks/safety.py:34-52 | 해석할 수 없는 외부 링크 조립을 실패 처리하지 않는다 | `scheme = getScheme(); host = getHost(); link = scheme .. host; goal.Text = link`는 URL 검사와 하드코딩 검사를 모두 통과 | UI·전송 sink로 흐르는 미해석 문자열 조립은 보수적으로 거부하거나 외부 링크 가능성을 추적
