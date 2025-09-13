from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Union

class Settings(BaseSettings):
    # 서버 설정
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    RELOAD: bool = True
    SECRET_KEY: str
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # CORS 설정
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = []

    # 데이터베이스 설정
    DATABASE_URL: str
    SQLALCHEMY_DATABASE_URI: Optional[str] = None
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Supabase 설정
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_BUCKET: str = "autolms-file"

    # e-Class 설정
    ECLASS_USERNAME: str
    ECLASS_PASSWORD: str
    ECLASS_BASE_URL: str = "https://eclass.seoultech.ac.kr"
    ECLASS_ENCRYPTION_KEY: Optional[str] = None

    # 파일 설정
    DOWNLOAD_DIR: str = "./downloads"
    AUTO_DOWNLOAD: bool = False
    MAX_FILE_SIZE: int = 104857600  # 100MB
    ALLOWED_FILE_TYPES: str = ".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.zip,.rar,.7z,.txt,.jpg,.jpeg,.png,.gif"

    # 로깅 설정
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # 자동화 설정
    MAX_CONCURRENT_TASKS: int = 5
    CRAWL_INTERVAL: int = 3600  # 1시간(초 단위)
    REQUEST_TIMEOUT: int = 30  # HTTP 요청 타임아웃(초 단위)

    # 세션 설정
    SESSION_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', case_sensitive=True)

    def get_cors_origins(self) -> List[str]:
        """CORS 오리진을 리스트로 반환"""
        if isinstance(self.BACKEND_CORS_ORIGINS, str) and self.BACKEND_CORS_ORIGINS:
            return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",")]
        if isinstance(self.BACKEND_CORS_ORIGINS, list):
            return self.BACKEND_CORS_ORIGINS
        return []

settings = Settings()