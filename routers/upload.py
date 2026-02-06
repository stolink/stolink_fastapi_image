# 기존 이미지 업로드 라우터
# 기존 main.py의 /upload 엔드포인트를 분리

import uuid
import boto3
from fastapi import APIRouter, UploadFile, File

from config import get_settings

router = APIRouter(tags=["Upload"])


def get_s3_client():
    """S3 클라이언트 반환 - IAM Role 사용 (credentials 자동 감지)"""
    settings = get_settings()
    return boto3.client("s3", region_name=settings.AWS_REGION)


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """
    이미지 파일을 S3에 업로드하고 CloudFront URL 반환
    
    Args:
        file: 업로드할 이미지 파일
        
    Returns:
        {"url": CloudFront URL}
    """
    settings = get_settings()
    s3_client = get_s3_client()
    
    # 1. 고유한 파일명 생성 (중복 방지)
    file_extension = file.filename.split(".")[-1]
    file_name = f"{uuid.uuid4()}.{file_extension}"

    # 2. S3에 파일 업로드
    s3_client.upload_fileobj(
        file.file,
        settings.MEDIA_S3_BUCKET_NAME,
        file_name,
        ExtraArgs={"ContentType": file.content_type}
    )

    # 3. CloudFront URL 반환 (OAC가 설정된 경로)
    image_url = f"{settings.CLOUDFRONT_URL}/media/{file_name}"

    return {"url": image_url}
