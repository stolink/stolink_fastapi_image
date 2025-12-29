# Callback Service
# Sends results back to Spring Boot backend

import asyncio
import logging
from typing import Optional
import httpx

from app.schemas import ImageCallbackPayload

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 10.0


class CallbackService:
    """Service for sending callbacks to Spring Boot backend with retry support."""
    
    def __init__(self, max_retries: int = MAX_RETRIES, timeout: float = 30.0):
        """Initialize CallbackService.
        
        Args:
            max_retries: Maximum number of retry attempts for failed callbacks.
            timeout: HTTP request timeout in seconds.
        """
        self.timeout = timeout
        self.max_retries = max_retries
    
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
            callback_url: Callback URL (required)
            
        Returns:
            True if callback was successful
            
        Raises:
            ValueError: If callback_url is not provided
        """
        payload = ImageCallbackPayload(
            job_id=job_id,
            character_id=character_id,
            status="SUCCESS",
            image_url=image_url,
            error=None,
        )
        return await self._send_callback_with_retry(payload, callback_url)
    
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
            callback_url: Callback URL (required)
            
        Returns:
            True if callback was successful
            
        Raises:
            ValueError: If callback_url is not provided
        """
        payload = ImageCallbackPayload(
            job_id=job_id,
            character_id=character_id,
            status="FAILED",
            image_url=None,
            error=error,
        )
        return await self._send_callback_with_retry(payload, callback_url)
    
    async def _send_callback_with_retry(
        self, 
        payload: ImageCallbackPayload,
        callback_url: Optional[str] = None,
    ) -> bool:
        """Send callback with exponential backoff retry logic."""
        if not callback_url:
            logger.warning(f"No callback_url provided for job {payload.job_id}, skipping callback")
            return False
        
        last_error: Optional[Exception] = None
        
        for attempt in range(self.max_retries + 1):
            try:
                success = await self._send_callback(payload, callback_url)
                if success:
                    return True
                    
                # Non-retryable failure (e.g., 4xx response)
                if attempt == self.max_retries:
                    logger.error(
                        f"Callback failed after {self.max_retries + 1} attempts for job {payload.job_id}"
                    )
                    return False
                    
            except (httpx.TimeoutException, httpx.RequestError) as e:
                last_error = e
                if attempt == self.max_retries:
                    logger.error(
                        f"Callback failed after {self.max_retries + 1} attempts for job {payload.job_id}: {e}"
                    )
                    return False
            
            # Calculate exponential backoff with jitter
            backoff = min(INITIAL_BACKOFF_SECONDS * (2 ** attempt), MAX_BACKOFF_SECONDS)
            logger.warning(
                f"Callback attempt {attempt + 1} failed for job {payload.job_id}, "
                f"retrying in {backoff:.1f}s..."
            )
            await asyncio.sleep(backoff)
        
        return False
    
    async def _send_callback(
        self, 
        payload: ImageCallbackPayload,
        callback_url: str,
    ) -> bool:
        """Send a single callback attempt to Spring Boot."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                callback_url,
                json=payload.model_dump(by_alias=True),
                headers={"Content-Type": "application/json"},
            )
            
            if response.status_code in (200, 201, 202):
                logger.info(f"Callback sent successfully to {callback_url} for job {payload.job_id}")
                return True
            elif response.status_code >= 400 and response.status_code < 500:
                # Client errors are not retryable
                logger.error(
                    f"Callback returned client error {response.status_code}: {response.text}"
                )
                return False
            else:
                # Server errors may be retryable
                logger.warning(
                    f"Callback returned status {response.status_code}: {response.text}"
                )
                raise httpx.RequestError(f"Server error: {response.status_code}")


# Singleton instance
_callback_service: Optional[CallbackService] = None


def get_callback_service() -> CallbackService:
    """Get or create CallbackService singleton."""
    global _callback_service
    if _callback_service is None:
        _callback_service = CallbackService()
    return _callback_service
