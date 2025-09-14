"""
ID 생성 유틸리티 함수들
Composite Key 전략을 위한 ID 생성 및 파싱 함수들
"""

def generate_composite_id(base_id: str, item_id: str) -> str:
    """
    일반적인 Composite ID 생성

    Args:
        base_id: 기본 ID (예: course_id)
        item_id: 항목 ID (예: article_id)

    Returns:
        str: Composite ID (예: "CS101_123")
    """
    return f"{base_id}_{item_id}"


def generate_material_id(course_id: str, material_id: str) -> str:
    """
    강의자료용 Composite ID 생성
    
    Args:
        course_id: 강의 ID
        material_id: 원본 강의자료 ID (e-Class)
        
    Returns:
        str: Composite ID (예: "CS101_mat456")
    """
    return f"{course_id}_{material_id}"


def generate_notice_id(course_id: str, notice_id: str) -> str:
    """
    공지사항용 Composite ID 생성
    
    Args:
        course_id: 강의 ID  
        notice_id: 원본 공지사항 ID (e-Class)
        
    Returns:
        str: Composite ID (예: "CS101_not789")
    """
    return f"{course_id}_{notice_id}"


def parse_material_id(composite_id: str) -> list[str]:
    """
    강의자료 Composite ID 파싱
    
    Args:
        composite_id: Composite ID (예: "CS101_mat456")
        
    Returns:
        tuple[str, str]: (course_id, material_id)
    """
    if "_" not in composite_id:
        raise ValueError(f"Invalid material composite ID format: {composite_id}")
    
    return composite_id.split("_", 1)


def parse_notice_id(composite_id: str) -> tuple[str, str]:
    """
    공지사항 Composite ID 파싱
    
    Args:
        composite_id: Composite ID (예: "CS101_not789")
        
    Returns:
        tuple[str, str]: (course_id, notice_id)
    """
    if "_" not in composite_id:
        raise ValueError(f"Invalid notice composite ID format: {composite_id}")
    
    return composite_id.split("_", 1)


def is_valid_composite_id(composite_id: str) -> bool:
    """
    Composite ID 유효성 검사
    
    Args:
        composite_id: 검사할 ID
        
    Returns:
        bool: 유효한 형식인지 여부
    """
    if not composite_id or not isinstance(composite_id, str):
        return False
    
    parts = composite_id.split("_", 1)
    return len(parts) == 2 and all(part.strip() for part in parts)