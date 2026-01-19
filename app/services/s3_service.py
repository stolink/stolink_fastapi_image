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
    """Service for uploading images to AWS S3 or S3-compatible storage (MinIO)."""

    def __init__(self):
        settings = get_settings()

        # S3 클라이언트 설정 (MinIO 등 S3 호환 스토리지 지원)
        client_kwargs = {
            "region_name": settings.aws_s3_region,
        }

        # Custom endpoint (MinIO, LocalStack 등)
        if settings.s3_endpoint_url:
            client_kwargs["endpoint_url"] = settings.s3_endpoint_url

        # 인증 정보: S3 전용 자격증명 우선, 없으면 AWS 기본 자격증명, EC2 IAM Role 사용 시 생략 가능
        access_key = settings.s3_access_key_id or settings.aws_access_key_id
        secret_key = settings.s3_secret_access_key or settings.aws_secret_access_key
        if access_key and secret_key:
            client_kwargs["aws_access_key_id"] = access_key
            client_kwargs["aws_secret_access_key"] = secret_key

        self.s3_client = boto3.client("s3", **client_kwargs)

        self.bucket_name = settings.aws_s3_bucket_name
        self.region = settings.aws_s3_region
        self.endpoint_url = settings.s3_endpoint_url if settings.s3_endpoint_url else None
        
        # CloudFront URL 정규화 (항상 스킴 포함)
        self.cloudfront_url = None
        if settings.cloudfront_url:
            cf_url = settings.cloudfront_url.rstrip("/")
            if not cf_url.startswith(("http://", "https://")):
                cf_url = f"https://{cf_url}"
            self.cloudfront_url = cf_url

    def upload_image(
        self,
        image_bytes: bytes,
        prefix: str = "character",
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        character_id: Optional[str] = None,
    ) -> str:
        """
        Upload image to S3 and return CloudFront URL (or S3 URL if CloudFront not configured).

        Args:
            image_bytes: Image data as bytes
            prefix: Prefix for the filename (e.g., "character", "edited")
            user_id: User ID for hierarchical path
            project_id: Project ID for hierarchical path
            character_id: Character ID for hierarchical path

        Returns:
            CloudFront URL or S3 URL of the uploaded image

        Raises:
            ValueError: If user_id, project_id, or character_id is missing

        S3 Key Structure:
            media/{user_id}/{project_id}/{character_id}/{prefix}_{timestamp}.png
        """
        # 필수 필드 검증
        if not user_id or not project_id or not character_id:
            raise ValueError("user_id, project_id, character_id are required for S3 upload")

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{prefix}_{timestamp}.png"

            # Build hierarchical S3 key
            s3_key = f"media/{user_id}/{project_id}/{character_id}/{file_name}"

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=image_bytes,
                ContentType="image/png",
            )

            # URL 반환 우선순위: CloudFront > Custom Endpoint (MinIO) > S3
            if self.cloudfront_url:
                url = f"{self.cloudfront_url}/{s3_key}"
            elif self.endpoint_url:
                # MinIO 등 커스텀 엔드포인트 사용
                url = f"{self.endpoint_url.rstrip('/')}/{self.bucket_name}/{s3_key}"
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

        This method is designed for general file uploads via API endpoints.
        Unlike `upload_image()`, this method:
        - Does NOT require user_id/project_id/character_id (uses flat 'media/' path)
        - Accepts any file type (not just images)
        - Returns a dict response suitable for API responses

        Args:
            file: FastAPI UploadFile or file-like object with .file and .filename/.content_type
            prefix: Prefix for the S3 key (e.g., "media", "images")

        Returns:
            dict with message and cloudfront_url

        Raises:
            S3UploadError: If upload fails with descriptive error message
        """
        original_filename = getattr(file, 'filename', 'upload')

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 파일명에서 확장자 추출
            extension = original_filename.rsplit('.', 1)[-1] if '.' in original_filename else 'bin'
            file_name = f"{prefix}_{timestamp}.{extension}"
            s3_key = f"media/{file_name}"

            content_type = getattr(file, 'content_type', 'application/octet-stream')

            # Ensure file pointer is at the beginning (in case file was already read)
            file.file.seek(0)

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
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"Failed to upload file '{original_filename}' to S3: [{error_code}] {error_msg}")
            raise RuntimeError(
                f"S3 upload failed for file '{original_filename}': [{error_code}] {error_msg}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error uploading file '{original_filename}': {e}")
            raise RuntimeError(
                f"Unexpected error uploading file '{original_filename}': {e}"
            ) from e

    def download_image(self, url: str) -> bytes:
        """
        Download image from URL (S3 or external).

        Args:
            url: Image URL to download

        Returns:
            Image data as bytes
        """
        # URL 스킴 누락 방어 코드 (프로토콜이 없으면 https:// 기본 적용)
        if url and not url.startswith(("http://", "https://", "/")):
            # 도메인 형태인 경우 (마침표 포함)
            first_segment = url.split("/")[0]
            if "." in first_segment:
                 # 로컬호스트나 도커 서비스명인 경우 http, 그 외는 https
                scheme = "http" if "localhost" in first_segment or "minio" in first_segment else "https"
                url = f"{scheme}://{url}"
                logger.info(f"Fixed missing scheme in URL: {url}")

        # Docker 연결 문제 해결: localhost -> minio (또는 stolink-minio-local)
        # 로컬 Docker 환경에서 RabbitMQ로부터 받은 메시지의 URL이 localhost일 경우
        # 컨테이너 내부에서는 접속할 수 없으므로 서비스명으로 변환
        if "localhost" in url or "127.0.0.1" in url:
            old_url = url
            # docker-compose.local.yml의 서비스명 'minio' 사용
            url = url.replace("localhost", "minio").replace("127.0.0.1", "minio")
            logger.info(f"Converted Docker URL: {old_url} -> {url}")

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
