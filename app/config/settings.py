# Application Settings
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "StoLink Image Worker"
    debug: bool = False
    
    # AWS Configuration
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"  # Bedrock region
    aws_s3_bucket_name: str = ""
    aws_s3_region: str = "ap-northeast-2"  # S3 bucket region
    cloudfront_url: str = ""  # CloudFront distribution URL (e.g., https://xxx.cloudfront.net)
    
    # AWS Bedrock Model IDs (using Inference Profile for cross-region support)
    bedrock_claude_model_id: str = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
    bedrock_nova_canvas_model_id: str = "amazon.nova-canvas-v1:0"
    # Deprecated: Stability AI (replaced with Google Gemini)
    # bedrock_stability_replace_model_id: str = "stability.stable-image-search-replace-v1:0"
    
    # Google Gemini Configuration (for image editing)
    gemini_api_key: str = ""
    gemini_image_model_id: str = "gemini-2.5-flash-image"
    
    # RabbitMQ Configuration
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_image_queue: str = "stolink.image.queue"
    
    # Spring Boot Callback
    spring_callback_url: str = "http://localhost:8080/api/internal/ai/image/callback"
    
    @property
    def rabbitmq_url(self) -> str:
        return f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}/"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
