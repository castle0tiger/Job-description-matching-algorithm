# Project: 채용공고-지원자-매칭 알고리즘 — 프로젝트 컨텍스트

## 프로젝트 개요

채용공고(JD)와 이력서 PDF를 업로드하면 AI가 자동으로 지원자를 분류·점수화해주는 웹 서비스.
한국어 이력서 특화, 최대 30개 이력서 처리 기준으로 설계.

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| 백엔드 | FastAPI + Python 3.9.7 |
| AI | Google Gemini 2.5 Flash (REST API, `requests` 라이브러리) |
| DB | SQLite (`data/analyses.db`) |
| 프론트엔드 | 순수 HTML/JS (Node.js 8.x 구버전이라 React 빌드 없음) |
| 배포 | Railway → Render로 이전 (git push → 자동 배포) |
| 로컬 실행 | `uvicorn backend.main:app --reload`, 브라우저 `localhost:8000` |

---

## 프로젝트 구조

```
JDcandidate_algorism/
├── backend/
│   ├── main.py        # FastAPI 앱, 라우터, 분석 파이프라인 메인
│   ├── analyzer.py    # Gemini API 호출, JD·이력서 분석 → JSON 추출
│   ├── filter.py      # 하드 필터링 로직 (경력/학력/자격/연봉/영어)
│   ├── matcher.py     # AI 점수 산정 (가중치 적용, total_score Python 계산)
│   ├── models.py      # Pydantic 데이터 모델 전체 정의
│   ├── parser.py      # 파일 텍스트 추출 (PDF/DOCX/PPTX 지원)
│   └── database.py    # SQLite CRUD (분석 이력 저장/조회/삭제)
├── frontend/
│   ├── index.html     # 메인 UI (JD 업로드, 필터 설정, 가중치 설정, 이력서 업로드)
│   ├── results.html   # 분석 결과 표시 (접이식 카드, 점수, 강약점, 자기소개서 평가)
│   └── history.html   # 분석 이력 조회/검색/삭제
├── data/
│   └── analyses.db    # SQLite DB (Railway에서는 재시작 시 초기화 주의)
├── requirements.txt
├── render.yaml        # Render 배포 설정
├── .env               # GEMINI_API_KEY 보관 (git 제외)
└── .env.example
```

---

## 개발 히스토리 요약

### Phase 1 — 설계 확정
- **목적**: JD PDF + 이력서 PDF(최대 30개) → 자동 분류·점수화
- 초기에 Claude API 검토했다가 **Google Gemini API로 전환** (비용 이유)
- Node.js 8.x 구버전이라 React 불가 → **순수 HTML/JS** 채택
- 필터 기능 추가 요청: 경력, 나이, 학력, 자격증, 전직장 연봉

### Phase 2 — 로컬 구현
- FastAPI 백엔드 + pdfplumber 이력서 파싱
- Gemini로 JD 분석 → `JDRequirements`, 이력서 분석 → `CandidateProfile`
- 하드 필터 → 통과자에 한해 AI 점수 산정
- 초기 가중치: 스킬 40 / 경력 35 / 학력 15 / 기타 10

### Phase 3 — 버그 수정 (로컬)
- **학력 필터 버그**: 석사 졸업자가 "학사 이상" 조건에서 탈락 → `_parse_education_level()` 개선
- **연봉 필터**: 정보 없으면 탈락 → 정보 없으면 통과로 변경
- `run.bat` 한글 인코딩 문제 → 직접 uvicorn 명령으로 실행
- Gemini SDK → `requests` 라이브러리 직접 호출로 교체 (SDK 불안정)
- 싱글턴 Gemini 클라이언트 → 모듈마다 `dotenv` 로드

### Phase 4 — Railway 클라우드 배포
- `git push` → Railway 자동 배포
- 반복적인 crash 문제 → 첫 번째 커밋 행 환경변수 로딩 문제 해결
- Gemini API 429/503 에러 → 재시도 로직 추가 (`_RETRY_STATUS`, `_MAX_RETRIES=3`)
- **Railway 무료 플랜**: 당시 비동기 병렬 처리는 미구현(무료 플랜 한계), 이력서 30개 초과 업로드 어려움 → 이후 병렬 처리 구현 (아래 "핵심 설계 결정 사항" 참고)

### Phase 5 — 기능 확장
- **분석 이력 저장**: SQLite DB (`database.py`), 이력 조회·삭제 API, `history.html`
- **가중치 사용자 설정**: 스킬/경력/학력/도메인적합도/자기소개서 (0~100, 합계 무관)
- **기본 가중치**: 25/25/25/25/0 (자기소개서 기본 OFF)
- **JD 텍스트 직접 입력**: PDF 업로드 외에 직무/주요업무/지원자격/우대사항 4개 항목 텍스트 입력
- **파일 형식 확장**: PDF + DOCX + PPTX (마케팅·디자인 직군 포트폴리오 대응)

### Phase 6 — 점수 체계 정교화
- **"기타 종합" → "도메인 적합도(domain_fit_score)"**: 후보자가 일한 업종/산업군이 JD 도메인과 일치하는 정도 (경력 적합도와 분리: 경력은 "무슨 일을 했는가", 도메인은 "어떤 업종에서 일했는가")
- **자기소개서 평가 추가**: 이력서 PDF에 포함된 자기소개서를 집중 평가
  - `cover_letter_relevance`: 직무 연관성 (0-100)
  - `cover_letter_growth`: 성장 가능성·도전 경험 (0-100)
  - `cover_letter_logic`: 논리성·구체성 (0-100)
  - `cover_letter_score`: 3개 평균
- **total_score 계산 위치 변경**: AI가 계산하지 않고 Python에서 직접 계산 (가중치 반영 정확성 확보)

### Phase 7 — 필터 개선
- **학력 레벨 표기**: 고등학교 졸업 / 전문학사 졸업 / 학사 졸업 / 석사 졸업 / 박사 졸업
- **"필수 자격증" → "필수 자격 조건"**: 자격증뿐 아니라 스킬, 교육 이수, 외국어 성적 등 키워드 통합 검색
- **영어 점수 필터 추가**: 토익 최소 점수, 오픽 최소 등급, 토익스피킹 최소 등급

### Phase 8 — UX 폴리시
- 결과 카드 접이식(collapsible) — 기본 접힘, 클릭 시 펼침, 인쇄 시 자동 전개
- 이력 페이지에 1위 후보자 이름·점수 표시 (`database.py`에 `top_candidate_name/score` 컬럼 추가)
- 분석 진행 중 이력서 개수 + 예상 시간 표시 프로그레스 인디케이터
- PDF 인쇄 버튼 (`@media print` CSS)
- 필터/가중치 섹션 기본 열림 (기존 기본 닫힘 → 사용자 인지 문제 개선)
- 결과 페이지 추천 등급 분포 차트 (적극추천/추천/검토필요/미추천 막대 그래프)
- 이력 페이지 키워드 검색 + 기간 필터 (오늘/7일/30일/전체)
- 요약 카드 시각 개선 (아이콘, 컬러 배경, 부제 텍스트)
- 모바일 반응형: 점수 바 4개 → 2×2, 자기소개서 바 → 1열, 필터 입력 → 1열

### Phase 9 — 클라우드 배포 이전
- **Railway → Render 이전**: Railway 무료 크레딧 소진 임박으로 Render Free 플랜으로 이전
- `render.yaml` 추가, GitHub 저장소 연결, `GEMINI_API_KEY` 환경변수 설정
- **Render URL**: `https://job-description-matching-algorithm.onrender.com`
- Render Free 플랜 특성: 15분 비활성 시 슬립 (첫 요청에 30~50초 콜드스타트), SQLite 재시작 시 초기화 (Railway와 동일 조건)

### Phase 10 — 나이 필터·나이 데이터 제거
- **배경**: 채용 시 연령을 이유로 지원자를 거르는 것은 연령차별 소지가 있음
- **필터 제거**: UI 나이 범위 입력, `min_age`/`max_age` 폼·모델 필드, `filter.py` 나이 판정 삭제
- **데이터 제거**: 이력서 추출 프롬프트에서 `age` 제거, `CandidateProfile.age` 삭제, 결과 카드 나이 표시 삭제
- **채점 차단**: 채점 프롬프트에서 나이 줄 삭제 + "나이·생년을 평가·서술에 사용하지 말 것" 지시 추가
  (필터를 비워도 프롬프트에 나이가 들어가면 LLM 점수에 간접 반영될 수 있었음)

### Phase 11 — 후보 순위 안정화
- **문제**: 같은 이력서·필터·가중치로 다시 돌리면 1위가 8위로 떨어지는 등 순위 변동이 큼
- **원인**: Gemini 기본 샘플링 무작위성, 기준이 모호한 채점(특히 도메인 적합도), 동점자 다수, 그리고 간헐적 버그
  ("전문학사"를 학사로 오판정, AI 응답 타입 불일치로 후보 누락, 일시 오류 시 후보가 조용히 사라짐)
- **조치**: temperature 0 + seed 고정, 스킬·경력·도메인 점수 구간 기준표(5점 단위), AI 응답 타입 정규화,
  재시도 5회·지수 백오프, 점수 산정 실패 후보 화면 표시, 같은 점수는 공동 순위 표시
- **측정** (가상 이력서 20개 × 5회): 순위 상관 0.60→0.82, 상위3 일치도 26%→65%,
  후보별 총점 흔들림 평균 8.7→3.6점, 도메인 점수 흔들림 평균 24.2→5.0점
- **남은 과제**: 총 경력 미기재 이력서의 경력 연수 오산, 하위권 도메인 점수 흔들림 → Phase 12에서 처리

### Phase 12 — 경력 연수·도메인 점수 Python 계산
- **경력 연수** (`backend/experience.py`): AI는 회사별 시작·종료 연월만 추출, Python이 순 경력 계산
  - 공백 기간 제외, 겹친 기간은 한 번만, 시작·종료 달 포함(2019.03~2021.02 = 24개월), "현재"는 분석일
  - 인턴·아르바이트 제외 (정규직·계약직·프리랜서 포함), 연도만 있으면 연중(시작 7월·종료 6월)으로 계산하고 "기간 일부 추정" 표시
  - 기간을 하나도 못 읽으면 AI 추정값 사용("AI 추정" 표시). 경력 필터 비교·탈락 사유도 개월 단위
- **도메인 점수** (`backend/domain.py`): AI가 0~100을 고르지 않고, 경력마다 JD 도메인 요소별로 직접/간접/없음만 판정
  - JD 도메인 요소 = 업종·산업 분야만 1~3개 (예: 디지털병리 → 의료·병리, IT·AI·디지털). 협회 같은 기관 형태·직무는 제외 — 경력·스킬 점수에서 이미 평가
  - 요소별로 여러 경력 중 최고 판정 사용(융합 도메인 대응), 직접 1 / 간접 0.5 / 없음 0, 같은 판정 경력 합산 1년 미만이면 한 단계 낮춤, 요소 평균 × 100
  - 메인 화면 "도메인 평가 요소" 칸(쉼표 구분)에 입력하면 그 요소로 고정 (비우면 AI가 결정)
- **화면**: 결과 카드에 순 경력·회사별 기간·제외/추정 표시, 도메인 요소별 판정 배지, JD 평가 요소 표시
- **테스트**: `python -m unittest discover -s tests -t .` (경력 계산 15개, 도메인 계산 11개)

---

## 현재 시스템 동작 흐름

```
1. 사용자: JD (PDF or 텍스트 입력) + 이력서 파일들 업로드 + 필터·가중치 설정
2. POST /api/analyze 호출
3. backend: JD 텍스트 추출 → Gemini로 JDRequirements 생성
4. backend: 각 이력서 텍스트 추출 → Gemini로 CandidateProfile 생성 (최대 8개 동시 처리)
5. backend: apply_filter() — 하드 필터 적용 (탈락자는 이후 AI 점수 산정 건너뜀)
6. backend: match_candidate() — 필터 통과자에 한해 Gemini로 점수 산정 (최대 8개 동시 처리)
7. backend: Python에서 total_score = 가중치 적용 계산
8. backend: SQLite에 결과 저장
9. 프론트: results.html에 점수 순으로 카드 표시
```

---

## 핵심 설계 결정 사항

| 결정 | 이유 |
|------|------|
| Gemini REST API (`requests`) | Gemini SDK 불안정, 직접 HTTP 호출이 안정적 |
| total_score를 Python에서 계산 | AI가 가중치 무시하고 자체 계산하는 문제 발생 |
| 필터 미충족 정보(연봉, 영어)는 통과 | 이력서에 없는 정보로 탈락시키면 오탈락 발생 |
| 나이는 필터·추출·채점·표시 전 단계에서 제외 | 연령차별 소지, 채점 프롬프트 경유 간접 반영까지 차단 |
| Gemini temperature 0 + 채점 구간 기준표 | 같은 입력에 같은 순위가 나오도록 (재현성) |
| 같은 점수는 공동 순위 | 동점자 순위가 업로드 순서로 갈리는 것을 방지 |
| 경력 연수는 근무 기간으로 Python 계산 | AI 합산은 공백·겹침·누락 처리가 부정확하고 실행마다 달라짐 |
| 도메인은 요소별 객관식 판정 + Python 점수화 | 0~100 직접 채점은 애매한 후보에서 크게 흔들림, 융합 도메인 경력이 평균에 묻힘 |
| 이력서 파싱·점수 산정 병렬 처리 (동시 8개) | 순차 처리 대비 약 5배 단축, Render 무료 서버 CPU·메모리 한계로 상한 8 |
| 순수 HTML/JS 프론트엔드 | Node.js 8.x 환경, React 빌드 불가 |
| SQLite 분석 이력 | 재시작 시 초기화 (Render/Railway 무료플랜 임시 스토리지) |
| 자기소개서 가중치 기본 0 | 자기소개서 없는 이력서가 불이익 받지 않도록 |

---

## 로컬 실행 방법

```bash
# 프로젝트 루트에서
cd JDcandidate_algorism
# .env 파일에 GEMINI_API_KEY 설정 필요
uvicorn backend.main:app --reload
# 브라우저: http://localhost:8000
```

---

## 배포 방법

```bash
git add .
git commit -m "변경 내용"
git push
# Render가 자동으로 감지·배포 (GitHub main 브랜치 연동)
# 환경변수 GEMINI_API_KEY는 Render 대시보드 Environment에서 직접 설정
```

- **Render 대시보드**: https://dashboard.render.com
- **서비스 URL**: https://job-description-matching-algorithm.onrender.com
- **주의**: 무료 플랜은 15분 비활성 시 슬립 → 첫 요청 시 50초 내외 콜드스타트 발생

---

## 마지막으로 논의된 미완료 사항

- **필수 자격 조건 필터 확장**: 현재 단순 키워드 검색. LLM 기반 의미론적 매칭으로 확장 시 비용·지연 증가 우려로 보류. 사용자가 복잡한 조건 입력 시 오탐 가능성 존재.
- **SQLite 영구 저장**: 현재 서버 재시작 시 분석 이력 초기화. Fly.io 유료 볼륨 또는 외부 DB(PostgreSQL 등) 연동 시 해결 가능하나 미구현.
- **사용자별 이력 분리(로그인)**: 현재 모든 사용자가 동일한 분석 이력 공유. 로그인 기능 추가 시 분리 가능하나 보류.

---

## 환경 변수

```
GEMINI_API_KEY=...   # Google AI Studio에서 발급
```

키는 환경변수에서만 읽음 (하드코딩 fallback 키 없음). 요청 시 URL이 아닌 `x-goog-api-key` 헤더로 전달해 에러 메시지에 키가 노출되지 않음.
