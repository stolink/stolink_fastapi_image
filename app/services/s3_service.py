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
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_s3_region,
        )
        self.bucket_name = settings.aws_s3_bucket_name
        self.region = settings.aws_s3_region
    
    def upload_image(self, image_bytes: bytes, prefix: str = "character") -> str:
        """
        Upload image to S3 and return public URL.
        
        Args:
            image_bytes: Image data as bytes
            prefix: Prefix for the S3 key (e.g., "character", "edited")
            
        Returns:
            Public S3 URL of the uploaded image
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{prefix}_{timestamp}.png"
            s3_key = f"stolink-images/{file_name}"
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=image_bytes,
                ContentType="image/png",
            )
            
            # Return public URL
            url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            logger.info(f"Uploaded image to S3: {url}")
            return url
            
        except ClientError as e:
            logger.error(f"Failed to upload image to S3: {e}")
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
