# API Routes
# REST API endpoints for health check and manual image operations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File

from app.schemas import (
    ImageGenerateRequest,
    ImageEditRequest,
    ImageResponse,
    HealthResponse,
)
from app.services import get_image_service, get_s3_service
from app.consumers import get_image_consumer

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    consumer = get_image_consumer()
    return HealthResponse(
        status="healthy",
        rabbitmq_connected=consumer.is_connected,
    )


@router.get("/ready")
async def readiness_check():
    """Readiness check - verifies RabbitMQ connection."""
    consumer = get_image_consumer()
    if not consumer.is_connected:
        raise HTTPException(
            status_code=503,
            detail="RabbitMQ not connected"
        )
    return {"status": "ready"}


@router.post("/api/image/generate", response_model=ImageResponse)
async def generate_image(request: ImageGenerateRequest):
    """
    Manually trigger image generation (for testing).
    
    This endpoint bypasses the RabbitMQ queue and directly generates an image.
    """
    try:
        logger.info(f"Manual image generation request: {request.message[:50]}...")
        image_service = get_image_service()
        image_url = image_service.create_character_image(request.message)
        
        return ImageResponse(
            success=True,
            image_url=image_url,
        )
        
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        return ImageResponse(
            success=False,
            error=str(e),
        )


@router.post("/api/image/edit", response_model=ImageResponse)
async def edit_image(request: ImageEditRequest):
    """
    Manually trigger image editing (for testing).
    
    This endpoint bypasses the RabbitMQ queue and directly edits an image.
    """
    try:
        logger.info(f"Manual image edit request: {request.edit_request[:50]}...")
        image_service = get_image_service()
        image_url = image_service.edit_image(request.image_url, request.edit_request)
        
        return ImageResponse(
            success=True,
            image_url=image_url,
        )
        
    except Exception as e:
        logger.error(f"Image edit failed: {e}")
        return ImageResponse(
            success=False,
            error=str(e),
        )


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """
    Upload an image file to S3 and return the CloudFront URL.
    
    Args:
        file: The image file to upload
        
    Returns:
        dict with message and cloudfront_url
    """
    try:
        s3_service = get_s3_service()
        result = await s3_service.upload_file(file, prefix="upload")
        return result
        
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
