# Spring Boot Callback 클라이언트
# 이미지 생성 완료 후 Spring Boot 서버로 결과 전송

import logging
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum

import httpx

from config import get_settings

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """작업 상태"""
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class CallbackPayload:
    """
    Spring Boot로 전송할 Callback 데이터
    """
    job_id: str
    status: JobStatus
    image_url: Optional[str] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        """API 전송용 딕셔너리 변환 (camelCase)"""
        result = {
            "jobId": self.job_id,
            "status": self.status.value,
        }
        if self.image_url:
            result["result"] = {"imageUrl": self.image_url}
        if self.error_message:
            result["error"] = {"message": self.error_message}
        return result


class CallbackClient:
    """
    Spring Boot Callback 클라이언트
    - 비동기 HTTP 요청
    - 재시도 로직 포함
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.timeout = httpx.Timeout(30.0, connect=10.0)
    
    async def send_success(self, job_id: str, image_url: str) -> bool:
        """
        성공 Callback 전송
        
        Args:
            job_id: 작업 ID
            image_url: 생성된 이미지 S3 URL
            
        Returns:
            전송 성공 여부
        """
        payload = CallbackPayload(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            image_url=image_url
        )
        return await self._send(payload)
    
    async def send_failure(self, job_id: str, error_message: str) -> bool:
        """
        실패 Callback 전송
        
        Args:
            job_id: 작업 ID
            error_message: 에러 메시지
            
        Returns:
            전송 성공 여부
        """
        payload = CallbackPayload(
            job_id=job_id,
            status=JobStatus.FAILED,
            error_message=error_message
        )
        return await self._send(payload)
    
    async def _send(self, payload: CallbackPayload, retries: int = 3) -> bool:
        """
        Callback 전송 (재시도 로직 포함)
        
        Args:
            payload: 전송할 데이터
            retries: 최대 재시도 횟수
            
        Returns:
            전송 성공 여부
        """
        url = self.settings.SPRING_BOOT_CALLBACK_URL
        data = payload.to_dict()
        
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=data)
                    
                    if response.status_code == 200:
                        logger.info(f"✅ Callback 전송 성공: jobId={payload.job_id}")
                        return True
                    else:
                        logger.warning(
                            f"⚠️ Callback 응답 오류: status={response.status_code}, "
                            f"attempt={attempt + 1}/{retries}"
                        )
                        
            except httpx.RequestError as e:
                logger.error(
                    f"❌ Callback 전송 실패: {e}, attempt={attempt + 1}/{retries}"
                )
        
        logger.error(f"❌ Callback 전송 최종 실패: jobId={payload.job_id}")
        return False
