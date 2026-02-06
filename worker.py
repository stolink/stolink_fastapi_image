# Worker 메인 모듈
# RabbitMQ에서 메시지를 소비하고 이미지 생성 후 Callback 전송

import asyncio
import logging
import signal
from typing import NoReturn

from queue import get_rabbitmq_connection, close_rabbitmq_connection, ImageGenConsumer
from queue.consumer import ImageGenTask, TaskType
from callback import CallbackClient
from crews import CreateImageService, EditImageService

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 종료 시그널 플래그
shutdown_event = asyncio.Event()


def handle_shutdown(signum, frame):
    """종료 시그널 핸들러"""
    logger.info(f"🛑 종료 시그널 수신: {signum}")
    shutdown_event.set()


async def process_task(task: ImageGenTask) -> str:
    """
    이미지 생성/편집 작업 처리
    
    Args:
        task: 처리할 작업
        
    Returns:
        생성된 이미지 S3 URL
    """
    callback_client = CallbackClient()
    
    try:
        if task.task_type == TaskType.CREATE:
            # 새 이미지 생성
            logger.info(f"🎨 이미지 생성 시작: {task.message[:50]}...")
            service = CreateImageService()
            image_url = service.create_image(task.message, task.user_id)
            
        elif task.task_type == TaskType.EDIT:
            # 기존 이미지 편집
            logger.info(f"✏️ 이미지 편집 시작: {task.edit_request[:50]}...")
            service = EditImageService()
            image_url = service.edit_image(task.image_url, task.edit_request, task.user_id)
            
        else:
            raise ValueError(f"알 수 없는 작업 유형: {task.task_type}")
        
        # Spring Boot로 성공 Callback 전송
        await callback_client.send_success(task.job_id, image_url)
        
        return image_url
        
    except Exception as e:
        logger.error(f"❌ 작업 처리 실패: {e}")
        # Spring Boot로 실패 Callback 전송
        await callback_client.send_failure(task.job_id, str(e))
        raise


async def run_worker() -> NoReturn:
    """
    워커 메인 루프
    - RabbitMQ 연결
    - 메시지 소비 시작
    - 종료 시그널까지 실행
    """
    logger.info("🚀 Image Gen Worker 시작")
    
    try:
        # RabbitMQ 연결
        connection = await get_rabbitmq_connection()
        consumer = ImageGenConsumer(connection)
        await consumer.setup()
        
        # 메시지 소비 시작 (블로킹)
        await consumer.consume(process_task)
        
    except asyncio.CancelledError:
        logger.info("⚠️ 워커 취소됨")
    except Exception as e:
        logger.error(f"❌ 워커 오류: {e}")
        raise
    finally:
        await close_rabbitmq_connection()
        logger.info("👋 Image Gen Worker 종료")


def start_worker():
    """워커 시작 (동기 진입점)"""
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # 이벤트 루프 실행
    asyncio.run(run_worker())


if __name__ == "__main__":
    start_worker()
