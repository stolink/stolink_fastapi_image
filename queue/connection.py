# RabbitMQ 연결 관리
# 비동기 연결 풀 및 재연결 로직

import asyncio
import logging
from typing import Optional

import aio_pika
from aio_pika import RobustConnection
from aio_pika.abc import AbstractRobustConnection

from config import get_settings

logger = logging.getLogger(__name__)

# 전역 연결 인스턴스
_connection: Optional[AbstractRobustConnection] = None
_connection_lock = asyncio.Lock()


async def get_rabbitmq_connection() -> AbstractRobustConnection:
    """
    RabbitMQ 연결 반환 (싱글톤 패턴)
    - 자동 재연결 지원 (RobustConnection)
    - 연결이 없으면 새로 생성
    
    Returns:
        RabbitMQ 연결 인스턴스
    """
    global _connection
    
    async with _connection_lock:
        if _connection is None or _connection.is_closed:
            settings = get_settings()
            logger.info(f"🔗 RabbitMQ 연결 중: {settings.RABBITMQ_URL}")
            
            _connection = await aio_pika.connect_robust(
                settings.RABBITMQ_URL,
                client_properties={"connection_name": "stolink-fastapi-image"}
            )
            
            logger.info("✅ RabbitMQ 연결 성공")
    
    return _connection


async def close_rabbitmq_connection():
    """RabbitMQ 연결 종료"""
    global _connection
    
    if _connection and not _connection.is_closed:
        await _connection.close()
        logger.info("🔌 RabbitMQ 연결 종료")
    
    _connection = None
