# API Routes
# REST API endpoints for health check and manual image operations

import logging

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
        # None-safe string slicing for logging
        message_preview = (request.message[:50] + "...") if request.message else "(empty)"
        logger.info(f"Manual image generation request: {message_preview}")
        
        if not request.message:
            raise HTTPException(status_code=400, detail="Message is required for image generation")
        
        image_service = get_image_service()
        image_url = image_service.create_character_image(request.message)
        
        return ImageResponse(
            success=True,
            image_url=image_url,
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid request for image generation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")


@router.post("/api/image/edit", response_model=ImageResponse)
async def edit_image(request: ImageEditRequest):
    """
    Manually trigger image editing (for testing).
    
    This endpoint bypasses the RabbitMQ queue and directly edits an image.
    """
    try:
        # None-safe string slicing for logging
        edit_preview = (request.edit_request[:50] + "...") if request.edit_request else "(empty)"
        logger.info(f"Manual image edit request: {edit_preview}")
        
        if not request.edit_request:
            raise HTTPException(status_code=400, detail="Edit request is required")
        if not request.image_url:
            raise HTTPException(status_code=400, detail="Image URL is required")
        
        image_service = get_image_service()
        image_url = image_service.edit_image(request.image_url, request.edit_request)
        
        return ImageResponse(
            success=True,
            image_url=image_url,
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid request for image edit: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Image edit failed: {e}")
        raise HTTPException(status_code=500, detail=f"Image edit failed: {e}")


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
