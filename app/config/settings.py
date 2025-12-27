# Application Settings
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "StoLink Image Worker"
    debug: bool = False
    
    # AWS S3 Configuration (can use EC2 IAM Role if credentials are empty)
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-northeast-2"  # Default region
    aws_s3_bucket_name: str = ""
    aws_s3_region: str = "ap-northeast-2"  # S3 bucket region
    cloudfront_url: str = ""  # CloudFront distribution URL (e.g., https://xxx.cloudfront.net)
    
    # AWS Bedrock Configuration (separate credentials for Bedrock services)
    aws_bedrock_access_key_id: str = ""
    aws_bedrock_secret_access_key: str = ""
    aws_bedrock_default_region: str = "us-east-1"  # Bedrock region (Nova Canvas available here)
    
    # AWS Bedrock Model IDs (using Inference Profile for cross-region support)
    bedrock_claude_model_id: str = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
    bedrock_nova_canvas_model_id: str = "amazon.nova-canvas-v1:0"
    
    # Google Gemini Configuration (for image editing)
    gemini_api_key: str = ""
    gemini_image_model_id: str = "gemini-2.5-flash-image"
    
    # RabbitMQ Configuration (external server)
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_vhost: str = "stolink"  # VHost (without leading /)
    rabbitmq_image_queue: str = "stolink.image.queue"
    
    # Spring Boot Callback (via ALB)
    alb_dns_name: str = ""  # ALB DNS name (e.g., my-alb-123.ap-northeast-2.elb.amazonaws.com)
    
    @property
    def spring_callback_url(self) -> str:
        """Build Spring callback URL from ALB DNS name."""
        if not self.alb_dns_name:
            return "http://localhost:8080/api/internal/ai/image/callback"
        return f"http://{self.alb_dns_name}/api/internal/ai/image/callback"
    
    @property
    def rabbitmq_url(self) -> str:
        # URL encode the vhost (/ becomes %2F)
        vhost = self.rabbitmq_vhost if self.rabbitmq_vhost else ""
        return f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}/{vhost}"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
