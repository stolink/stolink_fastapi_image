# Google Gemini Service
# Provides image editing functionality using Gemini API (Nano Banana)

import base64
import io
import logging
from typing import Optional

from google import genai
from google.genai import types
from PIL import Image

from app.config import get_settings

logger = logging.getLogger(__name__)


class GeminiImageGenerationError(Exception):
    """Raised when Gemini fails to generate/edit an image."""
    pass


class GeminiService:
    """Service for interacting with Google Gemini for image editing."""
    
    def __init__(self):
        settings = get_settings()
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set. Please add it to your .env file.")
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_id = settings.gemini_image_model_id
        logger.info(f"[GeminiService] Initialized with model: {self.model_id}")
    
    def edit_image(self, image_bytes: bytes, edit_prompt: str) -> bytes:
        """
        Edit an image using Gemini's image generation capability.
        
        Gemini can edit images by providing the source image along with
        a text prompt describing the desired changes.
        
        Args:
            image_bytes: Source image as bytes (PNG/JPEG)
            edit_prompt: Description of changes to make (in English)
            
        Returns:
            Edited image as bytes (PNG)
            
        Raises:
            GeminiImageGenerationError: If image generation fails
        """
        try:
            logger.info(f"[GeminiService] Editing image with prompt: {edit_prompt[:100]}...")
            
            # Convert bytes to PIL Image for Gemini
            source_image = Image.open(io.BytesIO(image_bytes))
            
            # Generate edited image using Gemini
            # Gemini takes image + text prompt and generates a new image
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[edit_prompt, source_image],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )
            
            # Extract the generated image from response
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    # Gemini returns base64 encoded image
                    image_data = part.inline_data.data
                    
                    # Convert to PNG bytes
                    result_image = Image.open(io.BytesIO(image_data))
                    output_buffer = io.BytesIO()
                    result_image.save(output_buffer, format="PNG")
                    result_bytes = output_buffer.getvalue()
                    
                    logger.info(f"[GeminiService] Image edited successfully: {len(result_bytes)} bytes")
                    return result_bytes
                elif part.text is not None:
                    # Gemini might return text explanation along with image
                    logger.info(f"[GeminiService] Gemini response text: {part.text[:200]}")
            
            # If no image was returned
            raise GeminiImageGenerationError(
                "Gemini did not return an image. This might be due to content policy or invalid prompt."
            )
            
        except Exception as e:
            logger.error(f"[GeminiService] Image editing failed: {e}")
            raise GeminiImageGenerationError(f"Failed to edit image with Gemini: {e}") from e


# Singleton instance
_gemini_service: Optional[GeminiService] = None


def get_gemini_service() -> GeminiService:
    """Get or create GeminiService singleton."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
