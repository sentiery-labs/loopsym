# Loopsym 신규 사용자 UX 리뷰

- 리뷰 일자: 2026-07-19
- 초점: 처음 설치한 사용자가 첫 시뮬레이션 결과를 보기까지의 설치, 실행, 뷰어, 예제 경험
- 기준 상태: 저장소 `main` (`799fc7c`) 및 PyPI `loopsym==0.1.0`
- 성공 기준: Python만 준비된 사용자가 경로를 추측하지 않고 설치한 뒤, PI 예제를 열어 실행하고 Scope 파형을 확인한다.

## 결론

엔진과 데스크톱 뷰어 자체는 첫 시뮬레이션을 보여 줄 준비가 되어 있다. 현재 소스로 생성한 ex1 HTML은 Chrome에서 `file://`로 열어 실행했을 때 약 2초 안에 1,000 step 시뮬레이션을 끝내고 Scope 1개를 정상 표시했다. 실행 중 상태, 완료 메시지, 오류 재시도 경로도 갖춰져 있다.

가장 큰 문제는 그 제품 경험까지 이어지는 공식 경로가 배포 형태마다 끊긴다는 점이다. PyPI 설치자는 예제와 CLI를 받지 못하고, 소스 체크아웃 사용자는 빠른 시작에서 선언되지 않은 `matplotlib` 의존성에 걸리며, 현재 HEAD의 새 CLI를 사용해도 빈 캔버스에서 시작한다. 즉, 좋은 뷰어가 있지만 신규 사용자가 그 뷰어의 성공 상태에 도달하는 골든 패스가 아직 없다.

현재 상태의 최초 시뮬레이션 UX 평가는 **높은 마찰**이다. 0.1.1 릴리스 전에 설치부터 Scope까지 이어지는 단일 경로를 제품 계약으로 정하고, wheel 기반 CI로 고정하는 것이 우선이다.

## 주요 발견

### P0. PyPI 설치 후 실행할 수 있는 공식 첫 경험이 없다

실제 깨끗한 가상환경에서 `python -m pip install loopsym==0.1.0`은 성공했다. 그러나 배포 wheel에는 `loopsym/` 모듈과 `viewer.html`만 있고 다음 항목이 없다.

- `examples/` 예제 파일
- `loopsym/__main__.py`
- `loopsym` 콘솔 스크립트
- 예제를 받을 저장소 또는 홈페이지 링크

따라서 설치 직후 `python -m loopsym`은 `No module named loopsym.__main__`으로 실패한다. 반면 PyPI에 표시되는 README의 빠른 시작은 `cd loopsym` 후 `python3 examples/ex1_pi_closed_loop.py`를 실행하라고 한다 (`README.md:33-38`). wheel에는 그 경로가 없으며, README에는 clone URL이나 `pip install` 명령도 없다. `pip show loopsym`의 `Home-page` 역시 비어 있다 (`pyproject.toml:5-20`에 `[project.urls]` 없음).

현재 소스에는 CLI가 추가되어 있지만 (`pyproject.toml:22-23`, `loopsym/__main__.py`), `CHANGELOG.md:3-8`은 이를 0.1.1의 미발행 기능으로 명시한다. 동시에 `pyproject.toml:7`은 여전히 0.1.0이다. 신규 사용자에게 실제로 전달되는 제품과 저장소가 크게 다르며, 버전을 올리지 않은 채로는 같은 PyPI 버전에 개선분을 재업로드할 수도 없다.

**영향:** 사용자는 설치 성공 직후 무엇을 실행할지 알 수 없다. README를 따라도 파일이 없어 첫 시뮬레이션 전에 막힌다.

**권고:** 0.1.1 버전을 명시적으로 올려 CLI와 예제 자산을 wheel에 포함해 배포한다. 최소한 `loopsym` 또는 `loopsym --example pi`가 저장소 체크아웃 없이 실행 가능한 PI 모델을 열어야 한다. `[project.urls]`에 Repository, Documentation, Issues도 추가한다.

### P1. 소스 체크아웃용 빠른 시작도 깨끗한 환경에서 실패한다

빠른 시작은 설치 없이 ex1을 실행한다. 하지만 ex1은 시작과 동시에 `matplotlib`을 import한다 (`examples/ex1_pi_closed_loop.py:10-15`). 깨끗한 venv에서 문서 명령을 실행한 결과는 다음과 같았다.

```text
ModuleNotFoundError: No module named 'matplotlib'
```

`matplotlib`은 `examples` extra에 올바르게 선언되어 있지만 (`pyproject.toml:25-28`), README는 `pip install -e ".[dev]"`만 개발자용 한 줄로 소개하고 (`README.md:31`), 신규 사용자에게 `python -m pip install -e ".[examples]"`를 안내하지 않는다. Python 최소 버전, 가상환경 생성, Windows 명령 차이도 빠른 시작에 없다.

README의 두 번째 Python 예시는 코어만 설치해도 정상 실행되지만 (`README.md:40-56`), 성공 시 터미널 출력이 전혀 없다. `render_html()` 반환값을 출력하거나 브라우저로 열지 않기 때문에 사용자는 현재 디렉터리에 `diagram.html`이 생겼다는 사실을 알아차려야 한다.

**영향:** GitHub에서 clone한 사용자는 첫 명령에서 의존성 오류를 보고, PyPI 사용자는 대체 코드가 성공해도 결과 위치를 알기 어렵다.

**권고:** 설치와 첫 실행을 하나의 복사 가능한 블록으로 만든다. 예를 들면 다음 계약이 적절하다.

```bash
python -m venv .venv
python -m pip install "loopsym[examples]"
loopsym --example pi
```

CLI가 브라우저를 열고 PI 모델을 보여 주면 `matplotlib` 없이도 첫 Scope를 만들 수 있으므로, 더 나은 최종 형태는 코어 설치만으로 동작하는 `python -m pip install loopsym` + `loopsym --example pi`이다. PNG 생성 예제는 그 다음 선택 단계로 내린다.

### P1. 새 CLI의 기본 화면이 첫 성공을 돕지 않는다

현재 HEAD의 `loopsym` CLI는 좋은 방향이다. 크로미엄 앱 창 또는 기본 브라우저를 자동으로 열고 추가 GUI 의존성이 없다 (`loopsym/app.py:1-35`). 그러나 모델 없이 실행하면 빈 `Diagram()`을 HTML에 심는다 (`loopsym/app.py:38-43`). 임베드된 빈 객체는 뷰어의 `demoModel()` 폴백보다 우선하므로 (`loopsym/viewer.html:532-564`), 실제 시작 화면은 빈 캔버스다.

코드 주석은 “`초기 모델` 버튼으로 데모 로드 가능”이라고 하지만 버튼은 `initialModel`로 되돌릴 뿐이라 (`loopsym/viewer.html:1940-1947`) 빈 캔버스에서는 계속 빈 상태다. 빈 모델에서 실행을 눌러도 사용자가 기대한 제어 예제가 아니라 “모델에 Scope 블록이 없습니다”라는 결과만 보게 된다.

**영향:** CLI를 발견한 사용자도 블록 추가와 배선을 먼저 배워야 첫 결과를 볼 수 있다. 제품의 가장 강한 가치인 즉시 실행 가능한 시각적 폐루프가 초기 화면에 나타나지 않는다.

**권고:** 인자 없는 `loopsym`은 PI 데모를 열고, 명시적인 `loopsym --blank`가 빈 편집기를 열게 한다. “초기 모델”은 “되돌리기”로 이름을 바꾸고, 별도의 “예제” 메뉴에서 PI, 진자, 이산 PI 등을 선택하게 한다. 초기 화면의 데모는 ex1과 같은 정본에서 생성해 JS, Python 예제, JSON이 어긋나지 않게 한다.

### P1. 설치 방식, 뷰어 모드, 오프라인 경로가 한 문서에서 섞인다

README는 소스 체크아웃, PyPI 패키지, 브라우저 Pyodide, 로컬 FastAPI 서버, ROS2를 연속해서 설명하지만 각 절의 전제 조건을 분리하지 않는다.

- 로컬 서버 설치가 `pip install -e ".[server]"`로만 안내된다 (`README.md:97-100`). PyPI에서 README를 읽는 사용자의 현재 디렉터리에는 프로젝트가 없으므로 이 명령은 실패한다. 설치 패키지용 명령은 `python -m pip install "loopsym[server]"`이어야 한다.
- 서버를 시작한 뒤 어떤 뷰어를 어떻게 열어야 하는지 해당 절에는 없다. 사용자는 앞에서 생성한 HTML을 수동으로 찾아 열고 새로고침해야 한다.
- 첫 브라우저 실행이 CDN에서 Pyodide를 내려받는다는 중요한 조건은 빠른 시작이 아니라 아키텍처 설명 안에 있다 (`README.md:72-89`).
- 오프라인 안내는 `python tools/vendor_pyodide.py`만 강조한다. 현재 뷰어는 `file://`에서 로컬 vendored 사본을 쓰지 않고 CDN만 시도하므로 (`loopsym/viewer.html:1579-1596`), 오프라인에서는 HTTP로 서빙하거나 로컬 서버 모드로 실행해야 한다. 이 추가 단계가 빠져 있다.

**영향:** 사용자는 “HTML은 단독 동작”, “오프라인 사본 우선”, “서버 자동 감지”를 동시에 읽지만 어떤 조합이 자신의 설치 형태에서 유효한지 시행착오로 알아내야 한다.

**권고:** README를 `PyPI 빠른 시작`, `소스에서 개발`, `로컬 서버/실시간`, `오프라인 교실`, `ROS2`로 분리하고 각 절을 독립적으로 실행 가능하게 만든다. 장기적으로 `loopsym serve [model]`이 HTTP 페이지, WebSocket 서버, 브라우저 열기를 한 프로세스에서 처리하면 모드 전환 설명 대부분이 사라진다.

### P2. 예제는 많지만 탐색 순서와 전제 조건이 보이지 않는다

저장소에는 ex1부터 ex10까지 좋은 점진적 소재가 있다. 하지만 README의 구성 표는 ex1부터 ex6까지만 일부 나열하고 ex7~ex10의 학습 순서, 실행 시간, 추가 장비를 한눈에 보여 주지 않는다. `examples/README.md`도 없고, 생성되는 PNG/HTML은 gitignore 대상이라 설치 전에 결과 화면을 미리 볼 수 없다.

전제 조건도 예제 파일의 docstring에 흩어져 있다.

| 범위 | 역할 | 실제 전제 조건 |
|---|---|---|
| ex1~ex4 | 코어 개념과 배치 결과 | `matplotlib` 필요 |
| ex5 | 실시간 모드 | 약 3초 벽시계 실행, 라이브 뷰어는 server extra 필요 |
| ex6 | ROS2 turtlesim | ROS2, `rclpy`, turtlesim 필요 |
| ex7~ex9 | 드론, 센서, PX4 화이트박스 | 코어만으로 실행 가능, HTML 생성 |
| ex10 | 게임패드 비행 | current HEAD 전용 기능, server extra, 게임패드 필요 |

`course/README.md:32-38`도 Jupyter와 pytest를 바로 실행하라고 하지만 이를 설치하는 명령은 없다. 강의 자료를 첫 진입점으로 택한 학생은 별도의 환경 설명이 필요하다.

**권고:** `examples/README.md`에 난이도, 예상 시간, 의존성, 생성물, 다음 예제를 표로 정리한다. README 첫 화면에는 실제 뷰어와 Scope를 보여 주는 스크린샷 1장을 두고, “처음이면 ex1”을 명시한다. wheel에는 최소 PI/진자/이산 PI JSON을 패키지 데이터로 포함한다.

### P2. 뷰어는 데스크톱에서 좋지만 작은 화면과 키보드 접근성이 취약하다

1440x900에서는 팔레트, 캔버스, 속성, Scope가 명확하게 분리되고 모델도 읽기 쉽다. 반면 390x844에서 직접 캡처했을 때 고정 3열 레이아웃(`172px 1fr 248px`, `loopsym/viewer.html:139-145`) 때문에 캔버스가 약 80px로 줄고 속성 패널이 모델을 가렸다. PyFunction 대화상자도 `min-width: 560px`다 (`loopsym/viewer.html:294-303`). 반응형 레이아웃 규칙은 색상 테마 외에는 없다.

SVG 블록과 포트는 pointer 이벤트만 받고 focus 가능한 요소나 ARIA 역할이 아니다. Delete와 Space 단축키는 있지만 포인터로 먼저 선택해야 하므로 키보드만으로 블록 선택, 배선, 속성 편집을 완료할 수 없다. 실행 상태 영역도 `aria-live`가 없는 일반 `span`이다 (`loopsym/viewer.html:318-345`).

**영향:** 휴대폰/좁은 노트북에서는 모델 확인이 어렵고, 키보드 또는 보조기술 사용자는 핵심 편집 흐름에 접근하기 어렵다.

**권고:** 모바일 지원이 범위 밖이면 README에 최소 권장 폭과 데스크톱 전용임을 명시한다. 지원한다면 900px 이하에서 팔레트와 속성을 드로어로 바꾸고 캔버스를 전폭으로 둔다. 실행 상태에는 `role="status"`/`aria-live`를 주고, 블록을 focus 가능하게 만들어 선택과 삭제부터 키보드 경로를 제공한다.

## 잘 되어 있는 부분

- 코어 의존성이 0개라 설치 기반이 작고, GUI 프레임워크 없이 브라우저를 재사용하는 방향이 적절하다 (`pyproject.toml:20`).
- 생성 HTML에 Python 엔진 소스를 심어 모델 파일 하나로 공유할 수 있다 (`loopsym/viz.py:223-269`).
- 첫 Pyodide 로딩, 실행 중, 완료, 오류가 같은 상태줄에 표시되고 실패한 엔진 로드는 재시도할 수 있다 (`loopsym/viewer.html:1532-1608`, `1694-1732`).
- 로컬 서버 유무를 자동 감지하고 Browser/Local Server 상태를 표시하는 점은 모드 전환 부담을 줄인다 (`loopsym/viewer.html:1611-1635`).
- ex1은 성공 시 PNG/HTML 절대 경로와 최종값을 출력해 소스 체크아웃 사용자에게 명확한 검산점을 준다 (`examples/ex1_pi_closed_loop.py:43-54`).
- 뷰어 초기 도움말은 블록 추가, 연결, 편집, 서브시스템 진입까지 주요 조작을 한 곳에 보여 준다 (`loopsym/viewer.html:1396`).

## 권장 골든 패스

신규 사용자의 대표 경로는 아래 세 단계면 충분해야 한다.

1. `python -m pip install loopsym`
2. `loopsym --example pi` 또는 인자 없는 `loopsym`
3. 열린 뷰어에서 `실행`을 눌러 Scope 확인

뷰어는 처음 열릴 때 다음 정보를 짧게 보여 주면 된다.

- PI 폐루프가 이미 로드되어 있음
- 첫 실행에는 인터넷 연결과 Pyodide 초기화 시간이 필요함
- 완료 후 아래 Scope에 `ref`와 `y`가 표시됨

별도 안내 문구를 늘리기보다 실행 가능한 초기 상태와 상태줄 피드백으로 설명하는 편이 낫다. 사용자가 첫 성공을 본 뒤 빈 모델, Python 코드 생성, 서버/실시간, ROS2로 확장하게 한다.

## 실행 우선순위

### 0.1.1 릴리스 차단 항목

1. `pyproject.toml` 버전을 0.1.1로 올리고 current HEAD의 CLI를 wheel로 배포한다.
2. 인자 없는 CLI에 PI 데모를 로드하고 `--blank`, `--example`을 추가한다.
3. README 최상단에 PyPI 기준 3단계 빠른 시작과 첫 실행의 CDN 조건을 둔다.
4. `[project.urls]`와 최소 예제 JSON 패키지 데이터를 추가한다.
5. wheel을 설치한 깨끗한 venv에서 CLI와 첫 시뮬레이션을 검증하는 CI를 추가한다.

### 다음 개선

1. 소스 개발, examples extra, server extra, ROS2, 오프라인 절차를 별도 절로 분리한다.
2. 예제 카탈로그와 뷰어 스크린샷을 추가한다.
3. 서버 시작과 뷰어 열기를 `loopsym serve`로 통합한다.
4. 작은 화면 정책을 결정하고, 최소 키보드/상태 접근성을 보완한다.

## 수용 기준

- 새 venv에서 저장소 없이 `python -m pip install loopsym` 후 `loopsym`이 실행된다.
- 첫 화면에 연결 완료된 PI 모델과 Scope가 있고 빈 캔버스가 아니다.
- 인터넷 연결 시 첫 실행이 완료되어 `ref`, `y` 두 채널을 표시한다.
- 인터넷이 없으면 실패 이유와 하나의 유효한 복구 명령을 상태줄에 제시한다.
- `loopsym --help`가 빈 모델, 예제, JSON 열기, 서버 모드의 차이를 설명한다.
- source checkout 경로의 문서 명령은 깨끗한 venv에서 그대로 실행된다.
- CI가 sdist/wheel을 빌드하고 별도 venv에 wheel을 설치한 뒤 `loopsym --help`, PI 모델 렌더, 네이티브 시뮬레이션을 검사한다.
- 1024px 이상을 지원 범위로 정한다면 그 폭에서 팔레트, 모델, 속성, 실행 버튼이 겹치지 않는다. 모바일을 지원한다면 390px에서도 캔버스가 주 작업 영역으로 남는다.

## 검증 기록

| 검증 | 결과 |
|---|---|
| 깨끗한 venv에 PyPI `loopsym==0.1.0` 설치 | 성공 |
| 설치 wheel에서 `python -m loopsym --help` | 실패: `loopsym.__main__` 없음 |
| 설치 wheel 내용 | 예제, CLI entry point, `__main__.py` 없음 |
| 깨끗한 venv에서 source checkout의 ex1 실행 | 실패: `matplotlib` 없음 |
| 설치 wheel에서 README Python 코드 실행 | 성공하지만 터미널 출력 없음, HTML만 생성 |
| current HEAD에서 `python -m loopsym --help` | 성공 |
| current HEAD ex1 네이티브 실행 | 성공, `y(10s) = 1.0001886829364643` |
| current HEAD ex1 HTML의 Chrome 첫 실행 | 약 2초 후 1,000 step 완료, Scope 1개 표시 |
| 1440x900 뷰어 | 모델, 팔레트, 속성 패널 모두 정상 표시 |
| 390x844 뷰어 | 고정 측면 패널 때문에 캔버스가 실사용 불가 수준으로 축소 |
| current HEAD 전체 테스트 | `96 passed in 36.30s` |

현재 CI는 editable dev 설치와 ex1~ex4 실행은 검사하지만 (`.github/workflows/ci.yml:23-30`), 배포 wheel 설치, CLI entry point, 패키지 내 예제 자산, 실제 브라우저 레이아웃은 검사하지 않는다. 이번에 발견된 배포와 저장소의 차이가 통과할 수 있었던 이유다.
