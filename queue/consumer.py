# RabbitMQ 메시지 Consumer
# Image Gen Task Queue에서 메시지를 소비하고 처리

import json
import logging
from typing import Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

from aio_pika import IncomingMessage
from aio_pika.abc import AbstractRobustConnection, AbstractChannel, AbstractQueue

from config import get_settings

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """이미지 생성 작업 유형"""
    CREATE = "CREATE"  # 새 이미지 생성
    EDIT = "EDIT"      # 기존 이미지 편집


@dataclass
class ImageGenTask:
    """
    Image Gen Task 메시지 구조
    Spring Boot에서 전송하는 메시지 형식
    """
    job_id: str
    user_id: str
    task_type: TaskType
    # CREATE 작업용
    message: str | None = None
    # EDIT 작업용
    image_url: str | None = None
    edit_request: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "ImageGenTask":
        """딕셔너리에서 ImageGenTask 객체 생성"""
        payload = data.get("payload", {})
        return cls(
            job_id=data["jobId"],
            user_id=data.get("userId", "default"),
            task_type=TaskType(data["taskType"]),
            message=payload.get("message"),
            image_url=payload.get("imageUrl"),
            edit_request=payload.get("editRequest"),
        )


# 메시지 핸들러 타입 정의
MessageHandler = Callable[[ImageGenTask], Awaitable[str]]


class ImageGenConsumer:
    """
    Image Gen Task Queue Consumer
    - RabbitMQ에서 메시지 소비
    - 메시지를 파싱하여 핸들러로 전달
    - ACK/NACK 처리
    """
    
    def __init__(self, connection: AbstractRobustConnection):
        self.connection = connection
        self.channel: AbstractChannel | None = None
        self.queue: AbstractQueue | None = None
        self.settings = get_settings()
    
    async def setup(self):
        """채널 및 큐 설정"""
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=1)  # 한 번에 하나씩 처리
        
        # 큐 선언 (없으면 생성, durable=True로 영속성 보장)
        self.queue = await self.channel.declare_queue(
            self.settings.IMAGE_GEN_QUEUE_NAME,
            durable=True
        )
        
        logger.info(f"📥 큐 설정 완료: {self.settings.IMAGE_GEN_QUEUE_NAME}")
    
    async def consume(self, handler: MessageHandler):
        """
        메시지 소비 시작
        
        Args:
            handler: 메시지 처리 핸들러 함수 (ImageGenTask -> S3 URL)
        """
        if not self.queue:
            await self.setup()
        
        logger.info("🎧 메시지 대기 중...")
        
        async with self.queue.iterator() as queue_iter:
            async for message in queue_iter:
                await self._process_message(message, handler)
    
    async def _process_message(self, message: IncomingMessage, handler: MessageHandler):
        """
        개별 메시지 처리
        
        Args:
            message: RabbitMQ 메시지
            handler: 처리 핸들러
        """
        try:
            # 메시지 파싱
            body = json.loads(message.body.decode())
            task = ImageGenTask.from_dict(body)
            
            logger.info(f"📨 작업 수신: jobId={task.job_id}, type={task.task_type}")
            
            # 핸들러 호출 (이미지 생성/편집)
            result_url = await handler(task)
            
            logger.info(f"✅ 작업 완료: jobId={task.job_id}, url={result_url[:50]}...")
            
            # 성공 시 ACK
            await message.ack()
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ 메시지 파싱 실패: {e}")
            # 잘못된 메시지는 requeue하지 않음
            await message.reject(requeue=False)
            
        except Exception as e:
            logger.error(f"❌ 작업 처리 실패: {e}")
            # 처리 실패 시 requeue하여 재시도
            await message.reject(requeue=True)
