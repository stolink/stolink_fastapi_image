# AWS Bedrock Service
# Provides low-level access to AWS Bedrock models

import json
import base64
import logging
from typing import Optional
import boto3
from botocore.exceptions import ClientError

from app.config import get_settings

logger = logging.getLogger(__name__)


class BedrockService:
    """Service for interacting with AWS Bedrock models."""
    
    def __init__(self):
        settings = get_settings()
        
        # Bedrock has separate credentials (for cross-account or different region)
        bedrock_access_key = settings.aws_bedrock_access_key_id or settings.aws_access_key_id
        bedrock_secret_key = settings.aws_bedrock_secret_access_key or settings.aws_secret_access_key
        bedrock_region = settings.aws_bedrock_default_region
        
        if bedrock_access_key and bedrock_secret_key:
            self.bedrock_runtime = boto3.client(
                "bedrock-runtime",
                aws_access_key_id=bedrock_access_key,
                aws_secret_access_key=bedrock_secret_key,
                region_name=bedrock_region,
            )
        else:
            # EC2 IAM Role 사용 (인증 정보 없이 리전만 명시)
            self.bedrock_runtime = boto3.client(
                "bedrock-runtime",
                region_name=bedrock_region,
            )
        
        self.claude_model_id = settings.bedrock_claude_model_id
        self.nova_canvas_model_id = settings.bedrock_nova_canvas_model_id
        # Note: Stability AI (stability_replace_model_id) has been replaced with Google Gemini
    
    def invoke_claude(self, system_prompt: str, user_message: str) -> str:
        """
        Invoke Claude 3.5 Haiku for text generation (prompt engineering).
        
        Args:
            system_prompt: System prompt defining the assistant's role
            user_message: User's input message
            
        Returns:
            Generated text response
        """
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "system": system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            }
            
            response = self.bedrock_runtime.invoke_model(
                modelId=self.claude_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body)
            )
            
            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]
            
        except ClientError as e:
            logger.error(f"Claude invocation failed: {e}")
            raise
    
    def invoke_nova_canvas(self, prompt: str, negative_prompt: str = "") -> bytes:
        """
        Invoke Amazon Nova Canvas for image generation.
        
        Args:
            prompt: Text prompt for image generation
            negative_prompt: What to avoid in the image
            
        Returns:
            Generated image as bytes (PNG)
        """
        try:
            body = {
                "taskType": "TEXT_IMAGE",
                "textToImageParams": {
                    "text": prompt,
                    "negativeText": negative_prompt if negative_prompt else None,
                },
                "imageGenerationConfig": {
                    "numberOfImages": 1,
                    "width": 1024,
                    "height": 1024,
                    "cfgScale": 8.0,
                    "seed": 0,  # Random seed
                }
            }
            
            # Remove None values
            if body["textToImageParams"]["negativeText"] is None:
                del body["textToImageParams"]["negativeText"]
            
            response = self.bedrock_runtime.invoke_model(
                modelId=self.nova_canvas_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body)
            )
            
            response_body = json.loads(response["body"].read())
            # Nova Canvas returns base64 encoded image
            image_base64 = response_body["images"][0]
            return base64.b64decode(image_base64)
            
        except ClientError as e:
            logger.error(f"Nova Canvas invocation failed: {e}")
            raise
    
    # Note: invoke_stability_search_replace() method has been removed.
    # Image editing is now handled by GeminiService.edit_image()


# Singleton instance
_bedrock_service: Optional[BedrockService] = None


def get_bedrock_service() -> BedrockService:
    """Get or create BedrockService singleton."""
    global _bedrock_service
    if _bedrock_service is None:
        _bedrock_service = BedrockService()
    return _bedrock_service
