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


class ContentFilterError(Exception):
    """Raised when Stability AI content filter rejects the prompt."""
    pass


class BedrockService:
    """Service for interacting with AWS Bedrock models."""
    
    def __init__(self):
        settings = get_settings()
        self.bedrock_runtime = boto3.client(
            "bedrock-runtime",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        self.claude_model_id = settings.bedrock_claude_model_id
        self.nova_canvas_model_id = settings.bedrock_nova_canvas_model_id
        self.stability_replace_model_id = settings.bedrock_stability_replace_model_id
    
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
    
    def invoke_stability_search_replace(
        self, 
        image_bytes: bytes, 
        prompt: str,
        search_prompt: str,
    ) -> bytes:
        """
        Invoke Stability Image Search and Replace for image editing.
        
        Args:
            image_bytes: Source image as bytes
            prompt: Description of what to replace with
            search_prompt: Description of what to search/find in the image
            
        Returns:
            Edited image as bytes (PNG)
        """
        try:
            # Encode image to base64
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            
            body = {
                "image": image_base64,
                "prompt": prompt,
                "search_prompt": search_prompt,
                "output_format": "png",
            }
            
            response = self.bedrock_runtime.invoke_model(
                modelId=self.stability_replace_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body)
            )
            
            response_body = json.loads(response["body"].read())
            logger.info(f"[Stability Debug] Response keys: {response_body.keys()}")
            
            # Check for content filter rejection
            if "finish_reasons" in response_body:
                finish_reasons = response_body.get("finish_reasons", [])
                if any("Filter" in str(r) for r in finish_reasons):
                    logger.error(f"[Stability] Content filter triggered!")
                    logger.error(f"[Stability] search_prompt: {search_prompt}")
                    logger.error(f"[Stability] prompt: {prompt}")
                    raise ContentFilterError(
                        f"Stability AI rejected the prompt due to content filter. "
                        f"Avoid words like: scar, wound, injury, blood, cut, knife, etc. "
                        f"Rejected prompts - search: '{search_prompt}', replace: '{prompt}'"
                    )
            
            # Stability returns base64 encoded image
            if "images" not in response_body:
                logger.error(f"[Stability Debug] Unexpected response structure: {response_body}")
                raise Exception(f"Stability error: {response_body}")
                
            result_base64 = response_body["images"][0]
            return base64.b64decode(result_base64)
            
        except ClientError as e:
            logger.error(f"Stability Search & Replace invocation failed: {e}")
            raise


# Singleton instance
_bedrock_service: Optional[BedrockService] = None


def get_bedrock_service() -> BedrockService:
    """Get or create BedrockService singleton."""
    global _bedrock_service
    if _bedrock_service is None:
        _bedrock_service = BedrockService()
    return _bedrock_service
