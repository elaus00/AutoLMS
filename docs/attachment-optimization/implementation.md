# Attachment Optimization - Implementation Details

## 📋 구현 개요

fix/crawl_service 브랜치 머지 과정에서 HTTP Bearer 인증과 첨부파일 최적화 시스템을 로컬 방식으로 유지하며 구현한 과정을 상세히 기록합니다.

## 🔧 핵심 구현 사항

### 1. AttachmentRepository - Service Key 모드

**파일**: `app/db/repositories/attachment_repository.py`

```python
def __init__(self, use_service_key: bool = False):
    """
    첨부파일 저장소 초기화

    Args:
        use_service_key: True시 Supabase Service Key 사용 (관리자 권한)
    """
    if use_service_key:
        self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        logger.info("AttachmentRepository: Service Key 모드로 초기화")
    else:
        self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info("AttachmentRepository: 일반 모드로 초기화")
```

**주요 메서드**:
- `get_existing_attachment()`: 중복 첨부파일 확인
- `create_or_get_existing()`: 중복 방지 생성/조회
- Service Key 모드에서 모든 사용자 데이터 접근 가능

### 2. AttachmentOptimizationService

**파일**: `app/services/attachment_optimization_service.py`

```python
class AttachmentOptimizationService:
    """
    첨부파일 최적화 서비스
    - 중복 다운로드 방지
    - 사용자 권한 검증
    - 스토리지 효율성 향상
    """

    async def process_attachment_optimized(
        self,
        file_data: BinaryIO,
        filename: str,
        course_id: str,
        source_type: str,
        source_id: str,
        user_id: str
    ) -> Optional[str]:
        """
        첨부파일 최적화 처리

        1. 중복 파일 확인
        2. 권한 검증
        3. 저장 또는 기존 파일 URL 반환
        """
```

**핵심 로직**:
1. **중복 검사**: `course_id + source_type + source_id + filename` 기준
2. **권한 확인**: 사용자의 강의 수강 여부 검증
3. **원자적 처리**: 동시 요청 시 레이스 컨디션 방지

### 3. HTTP Bearer Authentication 복원

**파일**: `app/api/deps.py`

```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer_scheme = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    """
    HTTP Bearer 토큰으로 사용자 인증

    Args:
        credentials: Authorization: Bearer <token> 헤더
    """
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
```

**변경 사항**:
- `OAuth2PasswordBearer` → `HTTPBearer`
- Supabase JWT 검증 제거
- 로컬 JWT 매니저 사용

### 4. API 엔드포인트 통합

**Material/Assignment/Notice 엔드포인트**:

```python
@router.get("/{item_id}/attachments/{attachment_id}")
async def download_attachment(
    course_id: str,
    item_id: int,
    attachment_id: int,
    current_user: dict = Depends(get_current_user),
    storage_service: StorageService = Depends(get_storage_service)
) -> Any:
    """첨부파일 다운로드 URL 조회"""

    # 1. 강의 존재 확인
    # 2. 항목 확인 (material/assignment/notice)
    # 3. 첨부파일 다운로드 URL 조회
    download_url = await storage_service.get_download_url(attachment_id, current_user["id"])
    return {"download_url": download_url}
```

## 🔄 머지 과정 상세

### Phase 1: 브랜치 상태 백업
```bash
# 로컬 변경사항 백업
mkdir backup_local_changes/
cp -r app/db/repositories/ backup_local_changes/
cp -r app/services/attachment_optimization_service.py backup_local_changes/
cp app/api/deps.py backup_local_changes/
```

### Phase 2: 원격 코드 가져오기
```bash
git fetch origin fix/crawl_service
git reset --hard 0e11351  # 원격 커밋으로 하드 리셋
```

### Phase 3: 선택적 기능 복원
1. **HTTP Bearer 인증** 시스템 복원
2. **AttachmentRepository** Service Key 모드 추가
3. **AttachmentOptimizationService** 전체 복원
4. **Configuration** SUPABASE_SERVICE_KEY 추가

### Phase 4: API 호환성 수정
- `get_course(user_id, course_id)` → `get_course(course_id)` 시그니처 통일
- `MaterialRefreshResponse` 스키마 추가
- 모든 엔드포인트 응답 모델 정리

## 🛠️ 기술적 결정사항

### 1. Service Key 사용 이유
```python
# 일반 모드: 사용자별 데이터만 접근
# Service Key 모드: 모든 사용자 데이터 접근 가능 (최적화 필요)
if use_service_key:
    # 중복 검사를 위해 전체 첨부파일 데이터베이스 접근
    self.supabase = create_client(url, service_key)
```

### 2. 중복 방지 전략
```python
# UNIQUE 제약조건 활용
UNIQUE(course_id, source_type, source_id, original_filename)

# 원자적 처리
async def create_or_get_existing(self, **data):
    try:
        # INSERT 시도
        result = await self.create_attachment(data)
        return result, True  # 새 파일
    except IntegrityError:
        # 중복 시 기존 파일 조회
        existing = await self.get_existing_attachment(...)
        return existing, False  # 기존 파일
```

### 3. 권한 검증 로직
```python
async def check_user_course_access(self, user_id: str, course_id: str) -> bool:
    """
    사용자의 강의 접근 권한 확인

    1. 강의 존재 여부 확인
    2. 사용자 수강 여부 확인
    3. 권한 레벨 검증 (학생/강사)
    """
```

## 📊 성능 최적화

### 1. 중복 검사 효율화
- Database Index 활용
- 복합 키 기반 빠른 검색
- 메타데이터 캐싱

### 2. 동시성 처리
```python
# 레이스 컨디션 방지
try:
    # 원자적 INSERT 시도
    result = await repo.create_attachment(data)
except IntegrityError:
    # 중복 시 기존 데이터 조회
    result = await repo.get_existing_attachment(...)
```

### 3. 스토리지 최적화
- Supabase Storage 직접 통합
- 중복 파일 저장 방지
- 효율적인 다운로드 URL 생성

## 🔍 테스트 및 검증

### 1. 단위 테스트
- AttachmentOptimizationService 메서드별 테스트
- 중복 시나리오 검증
- 권한 검증 로직 테스트

### 2. 통합 테스트
- Postman을 통한 전체 플로우 테스트
- 동시 사용자 시나리오 테스트
- 오류 상황 처리 검증

### 3. 성능 테스트
- 100명 동시 접근 시뮬레이션
- 중복 방지 효과 측정
- 응답 시간 최적화

## 🚨 이슈 해결 과정

### 1. JWT 토큰 검증 오류
**문제**: Supabase JWT vs 로컬 JWT 충돌
**해결**: HTTP Bearer 방식으로 통일

### 2. Pydantic 검증 오류
**문제**: SUPABASE_SERVICE_KEY 필드 누락
**해결**: config.py에 필드 추가

### 3. API 시그니처 불일치
**문제**: get_course() 메서드 매개변수 차이
**해결**: 원격 방식으로 통일 (user_id 제거)

### 4. 응답 스키마 오류
**문제**: MaterialList 검증 실패
**해결**: MaterialRefreshResponse 스키마 추가

## 📝 코드 품질

### 1. 함수 문서화
```python
async def refresh_courses(self, user_id: str) -> List[Dict[str, Any]]:
    """
    이클래스에서 새 강의 목록을 가져와 파싱하고 저장 (크롤링/파싱/저장 담당)

    Args:
        user_id: 사용자 ID

    Returns:
        새로 가져온 강의 목록
    """
```

### 2. 에러 핸들링
- 명확한 예외 메시지
- 적절한 HTTP 상태 코드
- 로깅을 통한 디버깅 정보

### 3. 타입 힌트
- 모든 함수 매개변수 타입 명시
- 반환 타입 명시
- Optional/Union 적절한 사용

## ✅ 구현 완료 상태

- ✅ 중복 방지 시스템
- ✅ HTTP Bearer 인증
- ✅ Supabase Storage 통합
- ✅ 권한 검증 로직
- ✅ API 엔드포인트 통합
- ✅ 오류 처리 및 로깅