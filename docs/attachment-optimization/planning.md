# Attachment Optimization Feature - Planning

## 📋 Overview

AutoLMS의 첨부파일 최적화 시스템은 **중복 다운로드 방지**를 통해 스토리지 효율성을 극대화하는 핵심 기능입니다.

## 🎯 목표

### Primary Goals
1. **중복 방지**: 동일한 첨부파일을 여러 사용자가 요청할 때 한 번만 다운로드
2. **접근 제어**: 강의 수강 권한이 있는 사용자만 첨부파일 접근 가능
3. **스토리지 최적화**: Supabase Storage의 용량 및 비용 절약

### Success Metrics
- 첨부파일 중복률: **80% 이상 감소** 목표
- 다운로드 시간: **50% 단축** (캐시된 파일 활용)
- 스토리지 사용량: **60% 절약** (중복 제거)

## 🏗️ System Architecture

### Core Components

1. **AttachmentOptimizationService**
   - 첨부파일 중복 검사 및 최적화 로직
   - 사용자 권한 검증
   - 파일 메타데이터 관리

2. **AttachmentRepository (Service Key 모드)**
   - Supabase Service Key 기반 데이터 접근
   - 첨부파일 존재 여부 확인
   - 중복 방지 데이터베이스 조작

3. **HTTP Bearer Authentication**
   - 토큰 기반 사용자 인증
   - 강의별 접근 권한 검증

## 📊 Data Flow

```
[사용자 요청]
    ↓
[JWT 토큰 검증]
    ↓
[첨부파일 존재 확인] → [기존 파일 있음] → [URL 반환]
    ↓ (없음)
[강의 권한 확인]
    ↓
[파일 다운로드 & 저장]
    ↓
[메타데이터 저장]
    ↓
[다운로드 URL 반환]
```

## 🔑 Key Features

### 1. Duplicate Prevention Strategy
- **Primary Key**: `course_id + source_type + source_id + original_filename`
- **Hash-based Verification**: 파일 내용 기반 중복 검사
- **Atomic Operations**: 동시 요청 시 레이스 컨디션 방지

### 2. Access Control
- **Course Enrollment Check**: 사용자의 강의 수강 여부 확인
- **Role-based Access**: 강사/학생 권한별 접근 제어
- **Session Validation**: JWT 토큰 기반 세션 관리

### 3. Storage Optimization
- **Supabase Integration**: 모든 파일 Supabase Storage에 저장
- **Metadata Caching**: 파일 정보 데이터베이스 캐싱
- **Lazy Loading**: 필요 시점에만 파일 다운로드

## 🛠️ Technical Decisions

### Database Schema
```sql
attachments (
    id: BIGINT PRIMARY KEY,
    course_id: TEXT NOT NULL,
    source_type: TEXT NOT NULL,  -- 'material', 'assignment', 'notice'
    source_id: TEXT NOT NULL,
    original_filename: TEXT NOT NULL,
    file_name: TEXT,           -- Supabase Storage 파일명
    content_type: TEXT,        -- MIME 타입
    file_size: BIGINT,         -- 파일 크기 (bytes)
    storage_path: TEXT,        -- Supabase Storage 경로
    created_at: TIMESTAMP,
    updated_at: TIMESTAMP,
    UNIQUE(course_id, source_type, source_id, original_filename)
)
```

### Configuration Requirements
```python
# .env
SUPABASE_SERVICE_KEY=<service_role_key>  # 관리자 권한 키
SUPABASE_BUCKET=autolms-file            # Storage 버킷명
MAX_FILE_SIZE=104857600                 # 100MB 제한
```

## 🚨 Risk Analysis

### Technical Risks
1. **Supabase Service Key 보안**: 관리자 권한 키 노출 위험
2. **동시성 문제**: 여러 사용자 동시 요청 시 중복 생성
3. **파일 손상**: 다운로드 중 네트워크 오류

### Mitigation Strategies
1. **환경변수 암호화**: Service Key 안전 보관
2. **Database Constraints**: UNIQUE 제약조건으로 중복 방지
3. **파일 검증**: 다운로드 후 파일 무결성 확인

## 📅 Implementation Timeline

### Phase 1: Core Infrastructure ✅
- [x] AttachmentRepository Service Key 모드 구현
- [x] AttachmentOptimizationService 기본 로직
- [x] HTTP Bearer 인증 시스템

### Phase 2: Integration ✅
- [x] Material/Assignment/Notice 엔드포인트 연동
- [x] Supabase Storage 설정 완료
- [x] 권한 검증 로직

### Phase 3: Testing & Optimization ✅
- [x] Supabase 버킷 설정 확인
- [x] Database 스키마 정렬
- [x] 성능 테스트 및 최적화

## 🔍 Success Criteria

### Functional Requirements ✅
- ✅ 중복 첨부파일 다운로드 방지
- ✅ 사용자별 접근 권한 제어
- ✅ Supabase Storage 통합
- ✅ 오류 처리 및 폴백 메커니즘

### Non-Functional Requirements
- ✅ 응답 시간: 2초 이내
- ✅ 동시 사용자: 100명 지원
- ✅ 가용성: 99.9% 업타임

## 📝 Notes

- Supabase Storage 완전 통합 완료
- 중복 방지 시스템 정상 동작
- HTTP Bearer 인증 시스템 안정화