# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2025-09-13] - Syllabus System Enhancement

### Fixed
- Syllabus API JWT 토큰 기반 시스템 적용 (user_id 의존성 제거)
- 웹 방화벽 차단 문제 해결 (다른 크롤러와 동일한 우회 패턴 적용)
- 강의계획서 파싱 데이터가 DB 스키마와 맞지 않던 문제 수정
- 파싱된 데이터 필드들(year_semester, professor_name 등)이 null로 저장되던 문제 해결

### Changed
- `SyllabusService.get_syllabus()` → JWT 기반 `get_syllabus_by_course()` 메서드 추가
- 강의계획서 크롤링 방식: 직접 URL 접근 → 강의실 접근 후 Referer 설정 방식
- 데이터 매핑: JSON 필드 저장 → 개별 스키마 필드 매핑
- 파서 견고성 개선: 단일 패턴 → 다중 패턴 fallback 지원

### Enhanced
- `SyllabusParser`: 스타일 기반, 클래스 기반, 텍스트 기반, 테이블 기반 파싱 지원
- 방화벽 우회: `access_course()` → 메인 페이지 방문 → `referer` 설정 패턴 적용
- 스키마 매핑: 파싱된 데이터를 실제 DB 필드에 정확하게 매핑하는 로직 추가

---

## [Unreleased] - Auth System Refactor

### Added
- AES-256 암호화 기반 이클래스 비밀번호 보안 시스템
- Supabase JWT 통합 인증 시스템 (표준 JWT 토큰 사용)
- 강의자료 공유를 위한 Supabase RLS 권한 기반 접근 제어
- Changelog 기반 체계적 문서화 시스템
- 토큰 갱신(refresh) 기능 지원
- 사용자 플로우 다이어그램 및 API 문서

### Changed
- PostgreSQL User 모델 → Supabase 완전 통합
- UUID 임시 토큰 → Supabase JWT 표준 토큰  
- 랜덤 Supabase 비밀번호 → eclass_username 기반 비밀번호
- 복잡한 PostgreSQL 세션 관리 → 경량화된 JWT 검증
- 회원가입/로그인 플로우 → 이클래스 계정 연동 방식
- 사용자 경험: AutoLMS 로그인 → 이클래스 접속 인식

### Removed
- PostgreSQL User 모델 및 관련 리포지토리 (app/models/user.py, app/db/repositories/user_repository.py)
- 기존 UUID 기반 세션 관리 코드 (복잡한 PostgreSQL 세션 저장소)
- 복잡한 이중 저장소 구조 (PostgreSQL + Supabase 중복)
- 메모리 기반 세션 캐시 (JWT의 stateless 특성으로 불필요)

### Security
- 이클래스 비밀번호 AES 암호화 저장 (평문 저장 해결)
- Supabase JWT 표준 인증으로 토큰 보안 강화
- Row Level Security(RLS) 정책 기반 데이터 접근 제어

---

## [Previous] - Before Refactor

### Issues Identified
- 이클래스 비밀번호 평문 저장 (보안 취약점)
- PostgreSQL + Supabase 이중 저장소로 인한 데이터 일관성 문제
- 랜덤 생성 비밀번호로 인한 재로그인 불가 문제
- 복잡한 3중 사용자 관리 구조 (PostgreSQL + Supabase Auth + Supabase Table)