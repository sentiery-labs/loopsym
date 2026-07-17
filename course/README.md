# course/ — "시뮬레이터를 만들고, 그걸로 드론을 날린다" 수업 자료 [CLD-P22]

하이브리드 커리큘럼(`docs/curriculum_15weeks.md`)의 **전 주차(1~15) 자료**.
전반부(1~7주) = 학생이 미니 엔진을 바닥부터 제작, 후반부(8~15주) = 정식
loopsym 팔레트를 신호사슬 순서로 열며 드론을 날린다.

> ⚠ **배포 주의**: WORKPLAN §7-1 — 코어(loopsym)는 공개 후보지만
> **course/ (과제·채점기·정답)는 비공개 유료 콘텐츠 후보**다.
> repo 공개 전 이 폴더 분리를 결정할 것. 특히 `solutions/` 는 학생에게
> 절대 배포 금지.

## 구조

```
weekNN/
  weekNN.ipynb      # 수업 노트북 (목표/이론 요약/실습/과제/채점 셀)
  *.py              # [1~7주] 뼈대 코드 (# TODO — 학생이 채우는 파일) + 제공 코드
  weekNN_model.json # [8~15주] 모델 뼈대 — 뷰어로 완성해 '저장'으로 덮어쓰기 = 제출물
  test_weekNN.py    # 채점기 (pytest) — loopsym 정식 구현이 정답 오라클
solutions/          # 교사용 정답 (뼈대 파일 드롭인 대체) — 비공개!
tools/
  gen_given.py       # [1~7주] '제공 코드'/정답을 week07/mybs.py 에서 생성 (정본 1개)
  gen_notebooks.py   # 노트북 생성기 (내용 수정은 여기서)
  gen_week_models.py # [8~15주] 모델 뼈대/정답 JSON 생성 (정본 1개)
```

후반부 채점 방식: 채점기가 학생의 `weekNN_model.json` 을 `load_json` 으로
로드해 실행하고 ①구조(어느 블록이 어떻게 배선됐는가) ②거동(미션 판정)을
검사한다. 11주차 이후 잡음은 **seed 고정** (재현성). 14주차는 채점기가
기체 질량을 +30% 로 바꿔서도 돌린다 ("같은 다이어그램, 다른 기체").

## 학생 사용법 (주차별 동일)

```bash
cd course/week01
jupyter notebook week01.ipynb     # 노트북 따라가며 *.py 의 TODO 를 채운다
python -m pytest test_week01.py -q   # 전부 초록 = 이번 주 완료
```

## 강사/운영

- **채점**: 학생의 weekNN 폴더에서 `python -m pytest test_weekNN.py -q`
  (레포 루트가 PYTHONPATH 에 있어야 loopsym 오라클 임포트 가능 —
  course/weekNN 안에서 실행하면 채점기가 알아서 경로를 잡는다).
- **채점기 신뢰성**: `tests/test_course_graders.py` 가 자동 검증 —
  정답을 넣으면 전 주차 PASS, 뼈대 그대로면 전 주차 FAIL 이어야 한다.
  (CI 에서 상시 실행)
- **내용 수정 시**: 엔진 조각의 정본은 `week07/mybs.py` 하나다.
  고친 뒤 `python course/tools/gen_given.py` 로 제공/정답 파일을 재생성하고
  메타 테스트로 확인. 노트북은 `gen_notebooks.py` 수정 후 재생성.

## 설계 원칙 (curriculum_15weeks.md 의 구현)

- 각 주차 폴더는 **자기완결**: 지난주 완성본을 '제공 코드'로 포함 —
  뒤처진 학생도 매주 새로 출발할 수 있다.
- 채점 기준은 언제나 **정식 loopsym 과의 수치 비교** (오라클 방식) —
  7주차 브리지에서 회귀 기준값(ex1 y(10s)=1.000189, ex2 θ(8s)=0.306499)
  6자리 대조가 전반부 졸업 시험이다.
- 미니 엔진(mybs)은 loopsym 과 **비트 단위로 같은 결과**를 내도록
  의미론을 맞췄다 (2단계 평가 + RK4 동일 구현).
