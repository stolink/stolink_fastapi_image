# Pydantic Schemas for Image Tasks
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ImageAction(str, Enum):
    """Image task action types."""
    CREATE = "create"
    EDIT = "edit"


class ImageTaskMessage(BaseModel):
    """Message received from RabbitMQ image queue."""
    job_id: str = Field(..., alias="jobId")
    character_id: Optional[str] = Field(None, alias="characterId")
    project_id: str = Field(..., alias="projectId")
    action: ImageAction
    message: str = Field(..., description="Character description or edit request")
    image_url: Optional[str] = Field(None, alias="imageUrl", description="Existing image URL for edit action")
    edit_request: Optional[str] = Field(None, alias="editRequest", description="Edit request details")
    callback_url: Optional[str] = Field(None, alias="callbackUrl")
    
    class Config:
        populate_by_name = True


class ImageCallbackPayload(BaseModel):
    """Callback payload to send to Spring Boot."""
    job_id: str = Field(..., alias="jobId")
    character_id: Optional[str] = Field(None, alias="characterId")
    status: str  # "completed" or "failed"
    image_url: Optional[str] = Field(None, alias="imageUrl")
    error: Optional[str] = None
    
    class Config:
        populate_by_name = True
        by_alias = True


class ImageGenerateRequest(BaseModel):
    """Request body for manual image generation API."""
    message: str = Field(..., description="Character description")
    job_id: Optional[str] = Field(None, alias="jobId")
    character_id: Optional[str] = Field(None, alias="characterId")
    project_id: Optional[str] = Field(None, alias="projectId")


class ImageEditRequest(BaseModel):
    """Request body for manual image edit API."""
    image_url: str = Field(..., alias="imageUrl", description="Source image URL")
    edit_request: str = Field(..., alias="editRequest", description="Edit instructions")
    job_id: Optional[str] = Field(None, alias="jobId")
    character_id: Optional[str] = Field(None, alias="characterId")
    

class ImageResponse(BaseModel):
    """Response for image generation/edit APIs."""
    success: bool = True
    image_url: Optional[str] = Field(None, alias="imageUrl")
    error: Optional[str] = None
    
    class Config:
        populate_by_name = True
        by_alias = True


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    rabbitmq_connected: bool = Field(False, alias="rabbitmqConnected")
    
    class Config:
        populate_by_name = True
        by_alias = True
