# 통합 환경변수 설정
# 기존 stolink_fastapi_image 설정 + nano_banana AI 서비스 설정

import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    애플리케이션 설정 클래스
    - 기존 S3/CloudFront 설정
    - AI 서비스용 설정 (Gemini, Replicate, AWS)
    """
    
    # 기존 S3/CloudFront 설정
    AWS_REGION: str = "ap-northeast-2"
    MEDIA_S3_BUCKET_NAME: str = "novel-project-images"  # 이미지/영상 통합 버킷
    CLOUDFRONT_URL: str = ""
    
    # AI 서비스용 설정 (nano_banana에서 이관)
    GEMINI_API_KEY: str = ""
    REPLICATE_API_TOKEN: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    
    # RabbitMQ 설정
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    IMAGE_GEN_QUEUE_NAME: str = "image_gen_task_queue"
    
    # Spring Boot Callback 설정
    SPRING_BOOT_CALLBACK_URL: str = "http://localhost:8080/internal-callback"
    
    # .env 파일에서 환경변수 로드 (있으면 덮어씀)
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )


# 싱글톤 패턴으로 설정 인스턴스 관리
_settings: Settings | None = None


def get_settings() -> Settings:
    """설정 인스턴스 반환 (지연 초기화)"""
    global _settings
    if _settings is None:
        _settings = Settings()
        # CrewAI에서 사용할 수 있도록 환경변수 설정
        os.environ["GEMINI_API_KEY"] = _settings.GEMINI_API_KEY
        os.environ["REPLICATE_API_TOKEN"] = _settings.REPLICATE_API_TOKEN
    return _settings
