# 3D 월드 연동 통신 규약 v1 (WorldLink)

loopsym 다이어그램과 3D 월드 시뮬레이터(SENTIERY 3D 월드 등)를 **lockstep** 으로
묶는 TCP 규약이다. loopsym 이 시간의 주인이고 유일한 적분 주체다. 월드는 받은
자세 그대로 기체를 그리고, 그 자리에서 거리계·카메라·충돌 값을 돌려준다.

- loopsym 쪽 구현: `loopsym/world_protocol.py`(메시지 틀), `loopsym/world.py`(`WorldLink`, `Camera`), `loopsym/sensors.py`(`Rangefinder`)
- 월드 쪽(서버)은 이 문서만 보고 만들 수 있어야 한다. 문서와 코드가 다르면 문서를 고친 뒤 코드를 고친다.

## 1. 연결

- TCP 한 연결. **월드가 듣고(서버) loopsym 이 붙는다(클라이언트).** 월드를 먼저 켜 두고 loopsym 실행을 여러 번 되풀이한다.
- 기본 주소 `127.0.0.1`, 기본 포트 `9431`. 다른 컴퓨터에서 붙게 하려면 월드 쪽에서 명시적으로 켜야 한다.
- **loopsym v1 은 실행마다 새로 접속한다.** 실행이 끝나면 `bye` 를 보내고 닫은 뒤, 다음 실행에서 다시 `hello` 부터 한다. 파라미터를 바꿔 여러 번 돌리면 닫기와 다시 접속이 1 ms 안에 이어진다.
- 한 번에 loopsym 하나만 붙는다. 월드는 `bye` 나 연결 끊김(EOF)을 **받는 즉시**(소켓을 읽는 스레드에서) 그 접속을 끝난 것으로 본다. 앞 접속이 이렇게 끝난 뒤 온 새 접속은 받아야 한다. 접속을 하나씩 차례로 처리하면(앞 접속이 끝나야 다음 accept) 이 경쟁이 생기지 않는다. 앞 접속이 아직 열려 있는 동안 온 두 번째 접속만 `error` 를 보내고 닫는다.

순서:

```
loopsym                         월드
  │ ── hello ─────────────────▶ │   접속마다 한 번
  │ ◀──────────────── hello_ok ─│
  │ ── reset ─────────────────▶ │   실행마다 (같은 접속으로 여러 번 실행 가능)
  │ ◀──────────────── reset_ok ─│
  │ ── step (seq 0) ──────────▶ │
  │ ◀───────────── frame (seq 0)│   샘플마다 한 쌍
  │ ── step (seq 1) ──────────▶ │
  │ ◀───────────── frame (seq 1)│
  │            …                │
  │ ── bye ───────────────────▶ │   실행이 끝나면(정상·오류·정지 모두)
```

## 2. 메시지 틀

```
[u32 머리 길이][머리 JSON, UTF-8][u32 몸 길이][몸 바이트]
```

- 길이는 4 바이트 부호 없는 정수, **리틀 엔디언**.
- 머리는 문자열 `type` 을 가진 JSON 객체.
- 몸은 영상이 있을 때만 쓴다. 없으면 몸 길이 0.
- 머리 최대 65 536 바이트, 몸 최대 6 220 800 바이트(1920 × 1080 × 3). 넘으면 받는 쪽이 `error` 를 보내고 연결을 끊는다.
- 머리의 숫자는 유한한 값만 쓴다(NaN·Infinity 는 JSON 이 아니다). loopsym 은 기체 상태가 발산하면 보내지 않고 오류로 멈춘다.
- **메시지 하나는 한 번에 쓴다**(길이·머리·몸을 버퍼 하나로 모아 한 번의 쓰기). 아니면 `TCP_NODELAY` 를 켠다. 작은 쓰기를 나눠 보내면 Nagle 알고리즘과 상대의 지연 ACK 가 겹쳐 메시지마다 최대 ~200 ms 가 붙어 25 Hz 를 낼 수 없다. loopsym 은 `TCP_NODELAY` 를 켠다.

## 3. 메시지

| type | 방향 | 머리 키 |
|---|---|---|
| `hello` | loopsym → 월드 | `proto`(1), `vehicle`(`"quad"`), `rotors`(로터 수), `link_st`(연동 샘플 시간 s), `camera`(`null` 또는 `{width, height, hfov_deg, format, every, mount}`), `rangefinder`(`null` 또는 `{max_m}`) |
| `hello_ok` | 월드 → loopsym | `proto`, `world`(월드 이름), `origin` `{lat, lon, alt_m}`(NED 원점의 위경도·해발), `camera`(`null` 또는 `{width, height, fx, fy, cx, cy}` 픽셀 단위 내부 값), `app`(앱 이름·빌드 문자열) |
| `reset` | loopsym → 월드 | (없음) 실행 시작. 기체를 원점에 놓고 궤적·충돌 표시를 비운다 |
| `reset_ok` | 월드 → loopsym | (없음) `reset` 을 마쳤다 |
| `step` | loopsym → 월드 | `seq`(0 부터 1씩), `t`(s), `q` `[w,x,y,z]`, `p_ned` `[N,E,D]` m, `p_ned_prev`(앞 샘플 위치, 첫 샘플은 `p_ned` 와 같음), `v_ned` m/s, `omega_frd` `[p,q,r]` rad/s, `motors`(0..1, 로터 수만큼), `armed`(= `max(motors) > 0`) |
| `frame` | 월드 → loopsym | `seq`(받은 `step` 과 같음), `t`, `range_m`(m, `null` 가능), `range_valid`(bool), `ground_up_m`, `collided`(bool), `collided_with`(부딪힌 것 이름, `null` 가능), `camera`(`null` 또는 `{seq, width, height, format}`) + 몸 = 영상 |
| `bye` | 양쪽 | (없음) 실행 끝. 받은 쪽은 연결을 닫는다 |
| `error` | 양쪽 | `message`(사람이 읽는 이유). 보낸 쪽은 연결을 끊는다 |

값의 뜻:

- `camera.format`: `"gray8"`(1 바이트/픽셀) 또는 `"rgb8"`(3 바이트/픽셀, R G B 순). 몸 길이는 정확히 `width × height × 채널 수`. **0번 행이 영상 맨 위**, 행 안에서는 왼쪽부터.
- `camera.every`: N 이면 `seq % N == 0` 인 샘플에서만 찍는다. 찍지 않은 `frame` 은 `camera: null`, 몸 길이 0. `frame.camera.seq` 는 그 `step` 의 `seq`. 찍어야 할 샘플을 건너뛰거나 다른 샘플에 영상을 붙이면 loopsym 은 오류로 멈춘다(옛 영상으로 계속 날지 않게).
- `hello.camera` 가 `null` 이면 영상을 보내지 않는다(`frame.camera = null`, 몸 길이 0). `hello_ok.camera` 의 `width`·`height` 는 요청과 같아야 한다.
- `camera.mount`: `"body"` 는 기체에 붙어 함께 기운다. `"level"` 은 롤·피치를 빼고 요만 따라간다(짐벌).
- `range_m`, `range_valid`: 거리계 광선이 `max_m` 안에서 무언가에 맞으면 그 거리와 `true`. 안 맞으면 `range_valid = false`(`range_m` 은 `null` 이어도 됨). `hello.rangefinder` 가 `null` 이면 항상 `false`.
- `ground_up_m`: 기체 바로 아래 지면(건물 지붕 포함)의 높이, NED 원점 기준 위가 +.
- `collided`: 앞 샘플 위치(`p_ned_prev`)에서 지금 위치(`p_ned`)까지 쓸어 본 사이에 무언가와 닿았으면 `true`. 착지(지면·출발 패드에 내려앉음)는 충돌이 아니다.

## 4. 좌표

- **NED**: 원점 = 월드가 정한 출발 지점의 지면. N = 진북, E = 동, D = 아래.
- **자세 `q`**: FRD 기체축(F 기수, R 오른쪽, D 아래) → NED 로 돌리는 단위 쿼터니언 `[w, x, y, z]`.
- **카메라**: 기체 아래(FRD +z)를 본다. 영상의 위쪽 = 기체 앞(기수). 내부 값(`fx, fy, cx, cy`)은 `hello_ok.camera` 로 받는다. 이상적인 바늘구멍 모델이면 `fx = width / (2·tan(hfov/2))`, `cx = width/2`, `cy = height/2`.
- **거리계**: 기체 중심에서 기체 아래(FRD +z) 방향 광선. 기체 자신의 충돌체는 맞지 않는다.

## 5. 시간

- loopsym 의 `WorldLink` 샘플 시간 `link_st`(기본 0.04 s = 25 Hz, 시뮬레이션 `dt` 의 정수배)마다 `step`/`frame` 한 쌍을 주고받는다.
- 샘플 k 의 상태로 `step` 을 보내고 같은 `seq` 의 `frame` 을 기다린다. loopsym 의 센서 블록은 그 프레임을 **다음 샘플에** 내보낸다. 그래서 **월드 센서 값은 한 샘플 늦다.** 첫 샘플(t = 0)의 센서 출력은 "값 없음"이다.
- 배치 실행은 월드가 답하는 만큼 빨리 돈다. 실시간 실행은 벽시계에 맞춰 돈다.

## 6. 오류

- `hello.proto` 와 `hello_ok.proto` 가 다르면 양쪽 모두 두 번호를 적은 문장으로 멈춘다(월드는 `error` 를 보내고 닫는다).
- loopsym 은 `hello_ok` 를 30 s, `reset_ok`·`frame` 을 5 s 기다린다(블록 파라미터로 바꿀 수 있음). 넘으면 시각과 `seq` 를 적은 오류로 실행을 끝낸다.
- `frame.seq` 가 보낸 `step.seq` 와 다르면 loopsym 은 오류로 멈춘다.
- 영상 몸 길이가 `width × height × 채널 수` 와 다르거나 `frame.camera` 의 크기·형식이 요청과 다르면 loopsym 은 그 크기를 적은 오류로 멈춘다. 영상이 `every` 규칙과 다르게 오거나 빠져도 그 `seq` 를 적은 오류로 멈춘다.
- 어느 쪽이든 연결이 끊기면 상대는 그 실행을 끝낸다. 월드는 다음 접속을 기다린다.

## 7. 보안

- 기본은 `127.0.0.1` 에서만 듣는다.
- 메시지는 자세·설정·센서 값만 담는다. 코드나 명령을 실행하는 메시지는 없다.
- 머리·몸 크기 상한을 넘는 메시지는 읽지 않고 연결을 끊는다.

## 8. 예: `bye` 한 개의 바이트

```
0e 00 00 00  7b 22 74 79 70 65 22 3a 22 62 79 65 22 7d  00 00 00 00
머리 길이 14  {"type":"bye"}                              몸 길이 0
```
