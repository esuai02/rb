critical | tests/test_harness.py:199-202,253 | Q3-C1은 현재 합격하지 않음 | binding 2151b953 결과가 `exit 1; FAILED (errors=1)`, `shutil.copytree`에서 `Cannot allocate memory` 발생 | 가용 메모리·임시공간에서 151개 결함 시험을 재실행해 오류 0을 확인

major | harness/checks/server.py:443-461 | 원격 입력을 전역·속성에 대입한 뒤 검증해도 통과 가능 | `_first_work`는 `local x = ...`만 처리로 세며 `slot = x`, `obj.Value = x`는 건너뜀 | 핸들러 매개변수 관련 모든 대입·변경을 검증 전 작업으로 거부하고 해당 변이 추가

major | harness/checks/server.py:171-185 | `claimOnce`가 표시 후 값을 `false`로 되돌려 중복 지급해도 통과 | `true` 대입만 `writes`에 기록하고 이후 `claimed[slot] = false`를 검사하지 않음; 실제 변이에서 `_claim_once_errors`가 `[]` 반환 | 동일 키의 후속 재대입·초기화와 모든 거짓 표시를 거부하고 2회 대입 변이 추가

major | harness/source.py:61-67,210-223; harness/checks/i18n.py:230-241 | 데이터 모델의 UI 하드코딩 문구가 현지화 검사를 우회 | `TextLabel`의 `Text: "Start"`가 속성명 없이 문자열만 보존되고, `Start`는 `IDENTIFIER`라 `hardcoded_text`에서 제외됨 | 데이터 파일에서 UI 문구 속성의 키·클래스를 보존해 LocalizationTable 키가 아닌 값을 거부
