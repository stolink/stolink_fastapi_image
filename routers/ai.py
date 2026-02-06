# AI 이미지/비디오 생성 라우터
# nano_banana 기능을 FastAPI 엔드포인트로 노출

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from crews import CreateImageService, EditImageService, CreateVideoService

router = APIRouter(prefix="/ai", tags=["AI Generation"])


# === Request/Response 모델 ===

class CreateImageRequest(BaseModel):
    """이미지 생성 요청"""
    message: str  # 생성할 이미지에 대한 텍스트 설명
    user_id: Optional[str] = "default"  # 사용자 ID (S3 폴더 구분용)


class EditImageRequest(BaseModel):
    """이미지 편집 요청"""
    image_url: str  # 편집할 원본 이미지 S3 URL
    edit_request: str  # 편집 요청 텍스트
    user_id: Optional[str] = "default"  # 사용자 ID (S3 폴더 구분용)


class CreateVideoRequest(BaseModel):
    """비디오 생성 요청"""
    message: str  # 생성할 비디오에 대한 텍스트 설명
    user_id: Optional[str] = "default"  # 사용자 ID (향후 사용)


class AIResponse(BaseModel):
    """AI 생성 응답"""
    url: str  # 생성된 이미지/비디오 URL
    message: Optional[str] = None  # 추가 메시지


# === 엔드포인트 ===

@router.post("/image/create", response_model=AIResponse)
async def create_image(request: CreateImageRequest):
    """
    텍스트 프롬프트로 새 이미지 생성
    
    - CrewAI를 사용하여 프롬프트 최적화
    - Replicate Imagen-4 모델로 이미지 생성
    - S3에 업로드 후 URL 반환
    
    사용 예시:
    ```json
    {
        "message": "검은색 정장을 입은 20대 한국인 남성",
        "user_id": "user123"
    }
    ```
    """
    try:
        service = CreateImageService()
        image_url = service.create_image(request.message, request.user_id)
        return AIResponse(url=image_url, message="이미지가 성공적으로 생성되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 생성 실패: {str(e)}")


@router.post("/image/edit", response_model=AIResponse)
async def edit_image(request: EditImageRequest):
    """
    기존 이미지 편집
    
    - CrewAI를 사용하여 편집 프롬프트 최적화
    - Replicate Nano Banana 모델로 이미지 편집
    - S3에 업로드 후 URL 반환
    
    사용 예시:
    ```json
    {
        "image_url": "https://bucket.s3.region.amazonaws.com/path/to/image.png",
        "edit_request": "머리를 장발로 바꾸고 왼쪽 눈가에 흉터 추가",
        "user_id": "user123"
    }
    ```
    """
    try:
        service = EditImageService()
        image_url = service.edit_image(request.image_url, request.edit_request, request.user_id)
        return AIResponse(url=image_url, message="이미지가 성공적으로 편집되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 편집 실패: {str(e)}")


@router.post("/video/create", response_model=AIResponse)
async def create_video(request: CreateVideoRequest):
    """
    텍스트 프롬프트로 비디오 생성
    
    - CrewAI를 사용하여 비디오 프롬프트 최적화
    - Replicate Seedance-1-Lite 모델로 비디오 생성
    
    사용 예시:
    ```json
    {
        "message": "바다 위에서 우아하게 춤추는 발레리나, 석양 배경",
        "user_id": "user123"
    }
    ```
    
    Note: 현재 비디오는 Replicate URL로 직접 반환됩니다. (S3 업로드 미구현)
    """
    try:
        service = CreateVideoService()
        video_url = service.create_video(request.message, request.user_id)
        return AIResponse(url=video_url, message="비디오가 성공적으로 생성되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"비디오 생성 실패: {str(e)}")
