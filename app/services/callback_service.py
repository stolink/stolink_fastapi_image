# Callback Service
# Sends results back to Spring Boot backend

import logging
from typing import Optional
import httpx

from app.config import get_settings
from app.schemas import ImageCallbackPayload

logger = logging.getLogger(__name__)


class CallbackService:
    """Service for sending callbacks to Spring Boot backend."""
    
    def __init__(self):
        settings = get_settings()
        self.callback_url = settings.spring_callback_url
        self.timeout = 30.0
    
    async def send_success_callback(
        self,
        job_id: str,
        image_url: str,
        character_id: Optional[str] = None,
        callback_url: Optional[str] = None,
    ) -> bool:
        """
        Send successful image generation callback.
        
        Args:
            job_id: Job ID to report
            image_url: URL of the generated/edited image
            character_id: Optional character ID
            callback_url: Override callback URL if provided
            
        Returns:
            True if callback was successful
        """
        payload = ImageCallbackPayload(
            job_id=job_id,
            character_id=character_id,
            status="completed",
            image_url=image_url,
            error=None,
        )
        return await self._send_callback(payload, callback_url)
    
    async def send_failure_callback(
        self,
        job_id: str,
        error: str,
        character_id: Optional[str] = None,
        callback_url: Optional[str] = None,
    ) -> bool:
        """
        Send failed image generation callback.
        
        Args:
            job_id: Job ID to report
            error: Error message
            character_id: Optional character ID
            callback_url: Override callback URL if provided
            
        Returns:
            True if callback was successful
        """
        payload = ImageCallbackPayload(
            job_id=job_id,
            character_id=character_id,
            status="failed",
            image_url=None,
            error=error,
        )
        return await self._send_callback(payload, callback_url)
    
    async def _send_callback(
        self, 
        payload: ImageCallbackPayload,
        callback_url: Optional[str] = None,
    ) -> bool:
        """Send callback to Spring Boot."""
        url = callback_url or self.callback_url
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload.model_dump(by_alias=True),
                    headers={"Content-Type": "application/json"},
                )
                
                if response.status_code in (200, 201, 202):
                    logger.info(f"Callback sent successfully to {url} for job {payload.job_id}")
                    return True
                else:
                    logger.warning(
                        f"Callback returned status {response.status_code}: {response.text}"
                    )
                    return False
                    
        except httpx.TimeoutException:
            logger.error(f"Callback timeout for job {payload.job_id}")
            return False
        except httpx.RequestError as e:
            logger.error(f"Callback request failed for job {payload.job_id}: {e}")
            return False


# Singleton instance
_callback_service: Optional[CallbackService] = None


def get_callback_service() -> CallbackService:
    """Get or create CallbackService singleton."""
    global _callback_service
    if _callback_service is None:
        _callback_service = CallbackService()
    return _callback_service
