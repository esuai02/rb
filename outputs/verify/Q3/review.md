major | harness/source.py:107-149; harness/run.py:66-80 | 잘못된 `$path` 타입은 검사 실패로 기록되지 않고 `TypeError`로 실행기 전체를 중단시킨다 | `_mappings`가 `$path` 타입을 검증하지 않으며 `load_tree()`가 per-check 예외 처리 바깥에서 호출된다 | `$path`를 문자열로 검증해 `Tree.problems`로 거부하고 실행기에서 기록까지 진행한다

major | harness/checks/i18n.py:146-173,192-205 | 비인스턴스 객체의 대괄호 UI 속성 대입은 현지화 검사를 우회한다 | `script.Parent[prop] = value`에서 `prop="Text"`, `value="Ready"`처럼 모두 식별자 문자열이면 `_instance_names()` 대상이 아니고 일반 하드코드 검사도 통과한다 | 모든 대괄호 대입을 분석하고 해석된 `Text`는 UI 문구 검사로, 미해석 속성은 거부한다

major | harness/checks/analytics.py:53-78; harness/source.py:47-53 | `Analytics`라는 이름의 일반 서버 Script가 정식 분석 ModuleScript처럼 신뢰된다 | 판별이 basename `f.name == module`뿐이며 kind·정확한 경로를 확인하지 않아, 매개변수 이벤트를 플랫폼 API로 직접 보내도 허용될 수 있다 | 정식 `analytics_module_path`의 서버 전용 ModuleScript만 모듈로 신뢰하고 나머지는 호출자로 검사한다

major | harness/checks/safety.py:125-141 | 알려진 `math`/`Random` 별칭의 미해석 동적 멤버 난수가 통과한다 | `local R = math; local method = getMethod(); R[method]()`는 구체 경로·난수 메서드·대입 패턴 어느 것도 검출하지 않으며 동적 멤버 거부도 없다 | 난수 원천 별칭의 미해석 대괄호 멤버를 보수적으로 거부한다
