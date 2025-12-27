# S3 Service
# Handles image upload to AWS S3

import logging
from datetime import datetime
from typing import Optional
import boto3
from botocore.exceptions import ClientError
import requests

from app.config import get_settings

logger = logging.getLogger(__name__)


class S3Service:
    """Service for uploading images to AWS S3."""
    
    def __init__(self):
        settings = get_settings()
        
        # EC2 역할을 사용할 경우 인증 정보를 비워두면 자동으로 역할을 사용
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_s3_region,
            )
        else:
            # EC2 IAM Role 사용 (인증 정보 없이 리전만 명시)
            self.s3_client = boto3.client(
                "s3",
                region_name=settings.aws_s3_region,
            )
        
        self.bucket_name = settings.aws_s3_bucket_name
        self.region = settings.aws_s3_region
        self.cloudfront_url = settings.cloudfront_url.rstrip("/") if settings.cloudfront_url else None
    
    def upload_image(self, image_bytes: bytes, prefix: str = "character") -> str:
        """
        Upload image to S3 and return CloudFront URL (or S3 URL if CloudFront not configured).
        
        Args:
            image_bytes: Image data as bytes
            prefix: Prefix for the S3 key (e.g., "character", "edited")
            
        Returns:
            CloudFront URL or S3 URL of the uploaded image
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{prefix}_{timestamp}.png"
            s3_key = f"media/{file_name}"
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=image_bytes,
                ContentType="image/png",
            )
            
            # CloudFront URL 우선, 없으면 S3 URL 반환
            if self.cloudfront_url:
                url = f"{self.cloudfront_url}/{s3_key}"
            else:
                url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            
            logger.info(f"Uploaded image to S3: {url}")
            return url
            
        except ClientError as e:
            logger.error(f"Failed to upload image to S3: {e}")
            raise
    
    async def upload_file(self, file, prefix: str = "media") -> dict:
        """
        Upload a file (UploadFile or file-like object) to S3.
        
        Args:
            file: FastAPI UploadFile or file-like object with .file and .filename/.content_type
            prefix: Prefix for the S3 key (e.g., "media", "images")
            
        Returns:
            dict with message and cloudfront_url
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 파일명에서 확장자 추출
            original_filename = getattr(file, 'filename', 'upload')
            extension = original_filename.rsplit('.', 1)[-1] if '.' in original_filename else 'bin'
            file_name = f"{prefix}_{timestamp}.{extension}"
            s3_key = f"media/{file_name}"
            
            content_type = getattr(file, 'content_type', 'application/octet-stream')
            
            # upload_fileobj를 사용하면 메모리 내의 파일 객체를 바로 업로드
            self.s3_client.upload_fileobj(
                file.file,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': content_type}
            )
            
            # CloudFront URL 우선, 없으면 S3 URL 반환
            if self.cloudfront_url:
                url = f"{self.cloudfront_url}/{s3_key}"
            else:
                url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            
            logger.info(f"Uploaded file to S3: {url}")
            return {
                "message": "업로드 성공",
                "cloudfront_url": url
            }
            
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error uploading file: {e}")
            raise
    
    def download_image(self, url: str) -> bytes:
        """
        Download image from URL (S3 or external).
        
        Args:
            url: Image URL to download
            
        Returns:
            Image data as bytes
        """
        try:
            # Check if it's an S3 URL from our bucket
            if self.bucket_name in url:
                # Generate presigned URL for private access
                import re
                match = re.match(
                    rf'https://{self.bucket_name}\.s3\.{self.region}\.amazonaws\.com/(.+)', 
                    url
                )
                if match:
                    s3_key = match.group(1)
                    presigned_url = self.s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': self.bucket_name, 'Key': s3_key},
                        ExpiresIn=3600
                    )
                    response = requests.get(presigned_url)
                    response.raise_for_status()
                    return response.content
            
            # Regular URL download
            response = requests.get(url)
            response.raise_for_status()
            return response.content
            
        except Exception as e:
            logger.error(f"Failed to download image from {url}: {e}")
            raise


# Singleton instance
_s3_service: Optional[S3Service] = None


def get_s3_service() -> S3Service:
    """Get or create S3Service singleton."""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3Service()
    return _s3_service
