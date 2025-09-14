# API Changes - Attachment Optimization

## 📋 변경 사항 개요

첨부파일 최적화 시스템 구현 과정에서 발생한 API 변경사항을 상세히 기록합니다.

## 🔐 Authentication Changes

### Before: OAuth2PasswordBearer
```python
# app/api/deps.py (이전)
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    # Supabase JWT 검증 로직
    payload = supabase.auth.get_user(token)
```

### After: HTTPBearer
```python
# app/api/deps.py (현재)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer_scheme = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    # 로컬 JWT 매니저 검증
    token = credentials.credentials
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
```

**Breaking Changes**:
- ❌ Authorization 헤더 형식 변경: `Bearer <token>` 필수
- ❌ Token URL 엔드포인트 제거
- ✅ JWT 토큰 검증 방식 로컬로 통일

## 🏫 Course Service API Changes

### Before: User Context Required
```python
# CourseService 메서드 (이전)
async def get_course(self, user_id: str, course_id: str) -> Optional[Course]:
    # 사용자별 강의 조회
```

### After: Direct Access
```python
# CourseService 메서드 (현재)
async def get_course(self, course_id: str) -> Optional[Course]:
    # 직접 강의 조회
```

**API 엔드포인트 영향**:
- `GET /api/v1/courses/{course_id}/materials/`
- `GET /api/v1/courses/{course_id}/assignments/`
- `GET /api/v1/courses/{course_id}/notices/`

**Breaking Changes**:
- ❌ `user_id` 매개변수 제거
- ✅ 권한 검증은 인증 계층에서 처리

## 📎 New Attachment Endpoints

### 강의자료 첨부파일
```http
GET /api/v1/courses/{course_id}/materials/{material_id}/attachments/{attachment_id}
Authorization: Bearer <jwt_token>

Response:
{
    "download_url": "https://supabase.storage/object/..."
}
```

### 과제 첨부파일
```http
GET /api/v1/courses/{course_id}/assignments/{assignment_id}/attachments/{attachment_id}
Authorization: Bearer <jwt_token>

Response:
{
    "download_url": "https://supabase.storage/object/..."
}
```

### 공지사항 첨부파일
```http
GET /api/v1/courses/{course_id}/notices/{notice_id}/attachments/{attachment_id}
Authorization: Bearer <jwt_token>

Response:
{
    "download_url": "https://supabase.storage/object/..."
}
```

## 📊 Schema Changes

### Before: MaterialList Only
```python
# app/schemas/material.py (이전)
class MaterialList(BaseModel):
    materials: List[MaterialOut]
    total: int
```

### After: MaterialRefreshResponse Added
```python
# app/schemas/material.py (현재)
class MaterialRefreshResponse(BaseModel):
    materials: List[Any]  # 유연한 데이터 형식 지원
    total: int
    refresh_result: Optional[Any] = None  # 새로고침 결과

class MaterialList(BaseModel):
    materials: List[MaterialOut]
    total: int
    skip: int
    limit: int
```

**API 영향**:
- `GET /api/v1/courses/{course_id}/materials/refresh`
- Response model 명확화

## 🗄️ Database Schema Changes

### Attachments 테이블 (신규)
```sql
CREATE TABLE attachments (
    id BIGINT PRIMARY KEY,
    course_id TEXT NOT NULL,
    source_type TEXT NOT NULL,  -- 'material', 'assignment', 'notice'
    source_id TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_name TEXT,           -- Supabase Storage 파일명
    content_type TEXT,        -- MIME 타입
    file_size BIGINT,         -- 파일 크기 (bytes)
    storage_path TEXT,        -- Supabase Storage 경로
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(course_id, source_type, source_id, original_filename)
);
```

## ⚙️ Configuration Changes

### 환경 변수 추가
```env
# .env (추가된 설정)
SUPABASE_SERVICE_KEY=<service_role_key>
SUPABASE_BUCKET=autolms-file
MAX_FILE_SIZE=104857600
ALLOWED_FILE_TYPES=.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.zip,.rar,.7z,.txt,.jpg,.jpeg,.png,.gif
```

### Settings 클래스 업데이트
```python
# app/core/config.py
class Settings(BaseSettings):
    # 기존 설정...
    SUPABASE_SERVICE_KEY: Optional[str] = None  # 추가
    SUPABASE_BUCKET: str = "autolms-file"       # 추가
```

## 🔄 Dependency Changes

### 새로운 의존성 추가
```python
# app/api/deps.py
async def get_attachment_optimization_service() -> AttachmentOptimizationService:
    """첨부파일 최적화 서비스 의존성"""
    return AttachmentOptimizationService()
```

### 기존 의존성 수정
```python
# app/api/deps.py
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    """HTTP Bearer 토큰 기반 사용자 인증"""
```

## 📈 Response Format Changes

### 에러 응답 표준화
```json
{
    "detail": "강의를 찾을 수 없습니다.",
    "status_code": 404
}
```

### 성공 응답 형식
```json
{
    "download_url": "https://supabase.storage/object/...",
    "expires_in": 3600
}
```

## 🚨 Breaking Changes Summary

### 인증 시스템
- ❌ `OAuth2PasswordBearer` → `HTTPBearer`
- ❌ Supabase JWT → Local JWT
- ❌ Token URL 엔드포인트 제거

### API 시그니처
- ❌ `get_course(user_id, course_id)` → `get_course(course_id)`
- ❌ 사용자 컨텍스트 매개변수 제거

### 스키마 변경
- ✅ `MaterialRefreshResponse` 스키마 추가
- ✅ 첨부파일 관련 필드 추가

## 📋 Migration Guide

### 클라이언트 업데이트 필요사항

1. **인증 헤더 변경**
   ```javascript
   // Before
   headers: {
       'Authorization': `Bearer ${token}`
   }

   // After (동일하지만 검증 로직 변경)
   headers: {
       'Authorization': `Bearer ${localJwtToken}`
   }
   ```

2. **API 엔드포인트 활용**
   ```javascript
   // 새로운 첨부파일 다운로드
   GET /api/v1/courses/{courseId}/materials/{materialId}/attachments/{attachmentId}
   ```

3. **에러 핸들링 업데이트**
   ```javascript
   // 표준화된 에러 응답 처리
   if (response.status === 404) {
       console.error(response.data.detail);
   }
   ```

## ✅ 호환성 매트릭스

| 기능 | 이전 버전 | 현재 버전 | 호환성 |
|------|-----------|-----------|--------|
| JWT 인증 | Supabase | Local | ❌ |
| Course API | user_id 필요 | course_id만 | ❌ |
| 첨부파일 다운로드 | 없음 | 신규 | ✅ |
| 스키마 응답 | 기본 | 확장 | ✅ |
| 에러 처리 | 비표준 | 표준화 | ✅ |