# Security Notes - Attachment Optimization

## 🔐 보안 개요

첨부파일 최적화 시스템 구현 시 적용된 보안 조치 및 고려사항을 상세히 기록합니다.

## 🛡️ 인증 시스템 보안

### JWT Token Management
```python
# 로컬 JWT 매니저 사용
JWT_SECRET_KEY = settings.SECRET_KEY  # 환경변수에서 로드
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.SESSION_EXPIRE_MINUTES
```

**보안 조치**:
- ✅ **비밀키 환경변수 관리**: `.env` 파일을 통한 안전한 키 보관
- ✅ **토큰 만료 시간 설정**: 1시간 기본값으로 세션 하이재킹 방지
- ✅ **알고리즘 고정**: HS256으로 토큰 변조 방지

### HTTP Bearer Authentication
```python
bearer_scheme = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    """
    HTTP Bearer 토큰 검증
    - 토큰 형식 검증
    - 서명 검증
    - 만료 시간 검증
    """
```

**보안 강화**:
- ✅ **토큰 형식 강제**: `Authorization: Bearer <token>` 형식 필수
- ✅ **자동 검증**: FastAPI의 내장 보안 스킴 활용
- ✅ **예외 처리**: 잘못된 토큰에 대한 명확한 오류 응답

## 🔑 Supabase Service Key 보안

### Critical Security Risk
```python
# SUPABASE_SERVICE_KEY는 관리자 권한을 가진 매우 민감한 정보
SUPABASE_SERVICE_KEY = "service_role.jwt_token"  # 모든 데이터 접근 가능
```

**보안 위험도**: 🔴 **CRITICAL**

### 보안 조치
1. **환경변수 암호화 저장**
   ```bash
   # .env 파일 권한 설정
   chmod 600 .env

   # git ignore 확인
   echo ".env" >> .gitignore
   ```

2. **접근 제한**
   ```python
   # Service Key는 최적화 서비스에서만 사용
   class AttachmentRepository:
       def __init__(self, use_service_key: bool = False):
           if use_service_key:
               # 관리자 권한 필요 시에만 사용
               self.supabase = create_client(url, service_key)
   ```

3. **로깅 제외**
   ```python
   # 로그에서 민감한 정보 제외
   logger.info("AttachmentRepository: Service Key 모드로 초기화")
   # ❌ logger.info(f"Service Key: {service_key}")
   ```

## 🚪 접근 제어 보안

### 강의 권한 검증
```python
async def check_user_course_access(self, user_id: str, course_id: str) -> bool:
    """
    사용자의 강의 접근 권한 확인

    보안 검증 단계:
    1. 사용자 존재 확인
    2. 강의 존재 확인
    3. 수강 등록 상태 확인
    4. 권한 레벨 확인
    """
```

**보안 계층**:
- ✅ **다중 검증**: 사용자 → 강의 → 권한 순차 확인
- ✅ **권한 기반 접근**: 수강하지 않은 강의 첨부파일 접근 차단
- ✅ **세션 검증**: JWT 토큰을 통한 사용자 신원 확인

### 첨부파일 접근 보안
```python
@router.get("/{material_id}/attachments/{attachment_id}")
async def download_material_attachment(
    course_id: str,
    material_id: int,
    attachment_id: int,
    current_user: dict = Depends(get_current_user),  # 인증 필수
    # ... 추가 의존성들
):
    # 1. 인증된 사용자만 접근 가능
    # 2. 강의 존재 여부 확인
    # 3. 자료 소유권 확인
    # 4. 첨부파일 접근 권한 확인
```

## 🗄️ 데이터베이스 보안

### Row Level Security (RLS)
```sql
-- Supabase RLS 정책 (권장)
CREATE POLICY "Users can only access their course attachments"
ON attachments FOR ALL
USING (
    course_id IN (
        SELECT course_id FROM enrollments
        WHERE user_id = auth.uid()
    )
);
```

**보안 이점**:
- ✅ **데이터베이스 레벨 보안**: 애플리케이션 우회 시도 차단
- ✅ **자동 필터링**: 사용자별 데이터 자동 격리
- ✅ **권한 기반 쿼리**: 접근 가능한 데이터만 조회

### 데이터 무결성
```sql
-- 중복 방지 제약조건
UNIQUE(course_id, source_type, source_id, original_filename)

-- NOT NULL 제약으로 필수 필드 보장
course_id TEXT NOT NULL,
source_type TEXT NOT NULL,
source_id TEXT NOT NULL,
original_filename TEXT NOT NULL
```

## 🔒 파일 보안

### 파일 타입 검증
```python
ALLOWED_FILE_TYPES = [
    ".pdf", ".doc", ".docx", ".ppt", ".pptx",
    ".xls", ".xlsx", ".zip", ".rar", ".7z",
    ".txt", ".jpg", ".jpeg", ".png", ".gif"
]

async def validate_file_type(filename: str) -> bool:
    """
    허용된 파일 타입만 업로드 가능

    보안 검증:
    - 확장자 화이트리스트 방식
    - MIME 타입 검증
    - 파일 시그니처 확인
    """
```

### 파일 크기 제한
```python
MAX_FILE_SIZE = 104857600  # 100MB

async def validate_file_size(file_data: bytes) -> bool:
    """
    파일 크기 제한으로 DoS 공격 방지

    보안 효과:
    - 스토리지 남용 방지
    - 네트워크 대역폭 보호
    - 서버 리소스 보호
    """
```

### 파일명 보안
```python
def sanitize_filename(filename: str) -> str:
    """
    파일명 보안 처리

    보안 조치:
    - 특수문자 제거/대체
    - 경로 순회 공격 방지 (../, ..\)
    - 시스템 예약어 처리
    """
    # 경로 순회 공격 방지
    filename = os.path.basename(filename)

    # 특수문자 대체
    safe_chars = re.sub(r'[^\w\-_\.]', '_', filename)

    return safe_chars
```

## 🌐 네트워크 보안

### HTTPS 강제
```python
# 프로덕션 환경에서 HTTPS 강제
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        HTTPSRedirectMiddleware,
        redirect_status_code=301
    )
```

### CORS 보안
```python
# 엄격한 CORS 정책
BACKEND_CORS_ORIGINS = [
    "https://yourdomain.com",
    "https://api.yourdomain.com"
]
# ❌ "*" (모든 도메인 허용) 사용 금지
```

### Rate Limiting (권장)
```python
# 첨부파일 다운로드 API에 대한 속도 제한
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """
    API 남용 방지를 위한 속도 제한
    - 사용자당 분당 요청 수 제한
    - 첨부파일 다운로드 특별 제한
    """
```

## 🔍 보안 로깅 및 모니터링

### 보안 이벤트 로깅
```python
import logging
security_logger = logging.getLogger("security")

# 보안 관련 이벤트 로깅
security_logger.warning(f"Failed authentication attempt from {client_ip}")
security_logger.info(f"User {user_id} accessed attachment {attachment_id}")
security_logger.error(f"Unauthorized access attempt to course {course_id}")
```

### 민감한 정보 로깅 방지
```python
# ✅ 좋은 예
logger.info(f"User {user_id} authenticated successfully")

# ❌ 나쁜 예 - 토큰 노출
logger.info(f"Token: {jwt_token}")

# ❌ 나쁜 예 - Service Key 노출
logger.info(f"Using service key: {service_key}")
```

## 🚨 보안 위험도 평가

### HIGH RISK 🔴
1. **Supabase Service Key 노출**
   - 영향: 전체 데이터베이스 접근 가능
   - 대응: 환경변수 암호화, 접근 로그 모니터링

2. **JWT Secret Key 노출**
   - 영향: 임의 사용자 토큰 생성 가능
   - 대응: 정기적 키 로테이션, 강력한 키 사용

### MEDIUM RISK 🟡
1. **권한 검증 우회**
   - 영향: 타 사용자 첨부파일 접근 가능
   - 대응: 다중 레이어 검증, RLS 정책 적용

2. **파일 업로드 남용**
   - 영향: 스토리지 남용, 서비스 거부
   - 대응: 파일 크기/타입 제한, 속도 제한

### LOW RISK 🟢
1. **로그 정보 노출**
   - 영향: 시스템 정보 유출
   - 대응: 민감한 정보 로깅 방지

## ✅ 보안 체크리스트

### 환경 설정
- [x] `.env` 파일 권한 600 설정
- [x] `.env` 파일 git ignore 처리
- [x] Service Key 환경변수 저장
- [x] JWT Secret Key 안전 보관

### 인증/인가
- [x] JWT 토큰 만료 시간 설정
- [x] HTTP Bearer 인증 구현
- [x] 강의별 권한 검증
- [x] 사용자 세션 관리

### 데이터 보안
- [x] 파일 타입 검증
- [x] 파일 크기 제한
- [x] 파일명 보안 처리
- [x] 데이터베이스 제약조건

### 네트워크 보안
- [x] CORS 정책 설정
- [ ] HTTPS 강제 (프로덕션)
- [ ] Rate Limiting 구현

### 모니터링
- [x] 보안 이벤트 로깅
- [x] 민감한 정보 로깅 방지
- [ ] 실시간 보안 모니터링