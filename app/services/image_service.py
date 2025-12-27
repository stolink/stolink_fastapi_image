# Image Service
# High-level service that uses LangGraph for orchestration

import logging
from typing import Optional, Dict, Any

from app.graph import get_image_graph

logger = logging.getLogger(__name__)


class ImageService:
    """Service for character image generation and editing using LangGraph."""
    
    def __init__(self):
        self.graph = get_image_graph()
    
    def create_character_image(self, message: str, job_id: Optional[str] = None, character_id: Optional[str] = None) -> str:
        """
        Create a new character image from description.
        
        Args:
            message: Character description (e.g., "검은색 정장을 입은 20대 한국인 남성")
            job_id: Optional job ID for tracking
            character_id: Optional character ID
            
        Returns:
            S3 URL of the generated image
            
        Raises:
            Exception: If image generation fails
        """
        logger.info(f"[ImageService] Creating character image for: {message[:50]}...")
        
        # Prepare initial state
        initial_state: Dict[str, Any] = {
            "action": "create",
            "message": message,
            "source_image_url": None,
            "enhanced_prompt": None,
            "search_prompt": None,
            "replace_prompt": None,
            "generated_image_bytes": None,
            "result_image_url": None,
            "error": None,
            "job_id": job_id,
            "character_id": character_id,
        }
        
        # Execute graph
        result = self.graph.invoke(initial_state)
        
        # Check for errors
        if result.get("error"):
            logger.error(f"[ImageService] Graph execution failed: {result['error']}")
            raise Exception(result["error"])
        
        if not result.get("result_image_url"):
            raise Exception("No image URL in result")
        
        logger.info(f"[ImageService] Character image created: {result['result_image_url']}")
        return result["result_image_url"]
    
    def edit_image(
        self, 
        image_url: str, 
        edit_request: str,
        job_id: Optional[str] = None,
        character_id: Optional[str] = None,
    ) -> str:
        """
        Edit an existing image based on the edit request.
        
        Args:
            image_url: URL of the source image
            edit_request: Edit instructions (e.g., "이 인물이 10년 후 모습을 보여줘")
            job_id: Optional job ID for tracking
            character_id: Optional character ID
            
        Returns:
            S3 URL of the edited image
            
        Raises:
            Exception: If image editing fails
        """
        logger.info(f"[ImageService] Editing image: {edit_request[:50]}...")
        
        # Prepare initial state
        initial_state: Dict[str, Any] = {
            "action": "edit",
            "message": edit_request,
            "source_image_url": image_url,
            "enhanced_prompt": None,
            "search_prompt": None,
            "replace_prompt": None,
            "generated_image_bytes": None,
            "result_image_url": None,
            "error": None,
            "job_id": job_id,
            "character_id": character_id,
        }
        
        # Execute graph
        result = self.graph.invoke(initial_state)
        
        # Check for errors
        if result.get("error"):
            logger.error(f"[ImageService] Graph execution failed: {result['error']}")
            raise Exception(result["error"])
        
        if not result.get("result_image_url"):
            raise Exception("No image URL in result")
        
        logger.info(f"[ImageService] Image edited: {result['result_image_url']}")
        return result["result_image_url"]


# Singleton instance
_image_service: Optional[ImageService] = None


def get_image_service() -> ImageService:
    """Get or create ImageService singleton."""
    global _image_service
    if _image_service is None:
        _image_service = ImageService()
    return _image_service
