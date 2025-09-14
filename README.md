# AutoLMS

서울과학기술대학교 e-Class 학습관리시스템의 공지사항, 강의자료, 과제 등을 자동으로 수집하고 관리하는 API 서버입니다.

## 주요 기능

- 강의 목록 자동 수집
- 공지사항, 강의자료, 과제 데이터 크롤링
- 첨부파일 자동 다운로드 및 Supabase 스토리지 업로드
- RestAPI를 통한 데이터 접근
- 백그라운드 크롤링 작업 지원
- Supabase Auth를 이용한 사용자 인증

## 기술 스택

- **백엔드**: FastAPI 0.115.0, Python 3.12+
- **데이터베이스**: PostgreSQL (SQLAlchemy 2.0 ORM, AsyncPG)
- **파일 스토리지**: Supabase Storage
- **인증**: Supabase Auth, JWT (python-jose)
- **비동기 처리**: asyncio, httpx 0.27.2
- **HTML 파싱**: BeautifulSoup4 4.12.3
- **데이터베이스 마이그레이션**: Alembic 1.14.0

## 설치 방법

1. 저장소 클론
```bash
git clone https://github.com/yourusername/AutoLMS.git
cd AutoLMS
```

2. 가상환경 생성 및 활성화 (Python 3.12 권장)
```bash
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

3. 의존성 설치
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 주요 의존성
- FastAPI 0.115.0
- SQLAlchemy 2.0.36 (비동기 ORM)
- AsyncPG 0.30.0 (PostgreSQL 비동기 드라이버)
- Pydantic 2.10.2 (데이터 검증)
- Uvicorn 0.32.1 (ASGI 서버)
- Python-Jose 3.3.0 (JWT 토큰 처리)
- Supabase 2.8.1 (BaaS)

4. 환경 변수 설정 (.env 파일 편집)
```
# 서버 설정
HOST=0.0.0.0
PORT=8000
RELOAD=true

# 데이터베이스 설정
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=autolms

# Supabase 설정
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
SUPABASE_BUCKET_NAME=autolms

# E-Class 설정
ECLASS_USERNAME=your_eclass_username
ECLASS_PASSWORD=your_eclass_password

# 암호화 키 (자동 생성됨)
ECLASS_ENCRYPTION_KEY=your_generated_key
```

5. 데이터베이스 마이그레이션
```bash
alembic upgrade head
```

## 실행 방법

```bash
# 가상환경 활성화 확인
source .venv/bin/activate

# 개발 모드 실행 (권장)
python main.py

# 또는 직접 uvicorn 사용
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

서버 실행 후 http://localhost:8000/docs 에서 Swagger UI를 통해 API 문서를 확인할 수 있습니다.

### 시스템 요구사항

- **Python**: 3.12 이상 (f-string, asyncio 완전 지원)
- **PostgreSQL**: 12 이상
- **메모리**: 최소 512MB RAM
- **저장 공간**: 최소 1GB (로그 및 캐시 포함)

## API 엔드포인트

기본 API URL: `/api/v1`

### 인증

- `POST /auth/register` - 사용자 등록
- `POST /auth/login` - 로그인 및 토큰 발급
- `POST /auth/logout` - 로그아웃

### 강의

- `GET /courses` - 모든 강의 목록 조회
- `GET /courses/{course_id}` - 특정 강의 정보 조회
- `POST /courses/refresh` - 강의 목록 새로고침

### 공지사항

- `GET /courses/{course_id}/notices` - 공지사항 목록 조회
- `GET /courses/{course_id}/notices/{notice_id}` - 특정 공지사항 상세 조회
- `POST /courses/{course_id}/notices/refresh` - 공지사항 새로고침

### 강의자료

- `GET /courses/{course_id}/materials` - 강의자료 목록 조회
- `GET /courses/{course_id}/materials/{material_id}` - 특정 강의자료 상세 조회
- `POST /courses/{course_id}/materials/refresh` - 강의자료 새로고침

### 과제

- `GET /courses/{course_id}/assignments` - 과제 목록 조회
- `GET /courses/{course_id}/assignments/{assignment_id}` - 특정 과제 상세 조회
- `POST /courses/{course_id}/assignments/refresh` - 과제 새로고침

### 첨부파일

- `GET /attachments/{attachment_id}` - 첨부파일 메타데이터 조회
- `GET /attachments/{attachment_id}/download` - 첨부파일 다운로드
- `GET /attachments/by-source/{source_type}/{source_id}` - 소스별 첨부파일 조회
- `GET /attachments/search` - 첨부파일 검색

### 크롤링

- `POST /crawl/all` - 모든 과목 크롤링 시작
- `POST /crawl/course/{course_id}` - 특정 과목 크롤링 시작
- `GET /crawl/status/{task_id}` - 크롤링 작업 상태 조회
- `POST /crawl/cancel/{task_id}` - 크롤링 작업 취소

## 프로젝트 구조

```
AutoLMS/
├── app/                 # 메인 애플리케이션
│   ├── api/            # API 엔드포인트
│   ├── core/           # 핵심 설정
│   ├── db/             # 데이터베이스 관련
│   ├── models/         # 데이터 모델
│   ├── schemas/        # Pydantic 스키마
│   └── services/       # 비즈니스 로직
├── tests/              # 테스트 파일들
├── scripts/            # 설정 및 유틸리티 스크립트
├── sql/                # SQL 스크립트
├── api-docs/           # API 문서 (Postman 컬렉션)
├── test_data/          # 테스트 데이터
└── alembic/            # 데이터베이스 마이그레이션
```

## 개발자 문서

- **API 문서**: `/docs` 엔드포인트 또는 `api-docs/` 폴더의 Postman 컬렉션
- **테스트**: `tests/README.md` 참조
- **스크립트**: `scripts/README.md` 참조
- **SQL**: `sql/README.md` 참조

## 라이선스

MIT
