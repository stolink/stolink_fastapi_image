# RabbitMQ Image Queue Consumer
# Consumes image generation/editing tasks from the queue

import asyncio
import json
import logging
from typing import Optional

import aio_pika
from aio_pika import Message, IncomingMessage

from app.config import get_settings
from app.schemas import ImageTaskMessage, ImageAction
from app.services import get_image_service, get_callback_service

logger = logging.getLogger(__name__)


class ImageConsumer:
    """Consumer for RabbitMQ image queue."""
    
    def __init__(self):
        settings = get_settings()
        self.rabbitmq_url = settings.rabbitmq_url
        self.queue_name = settings.rabbitmq_image_queue
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.queue: Optional[aio_pika.Queue] = None
        self._running = False
    
    async def connect(self) -> bool:
        """Establish connection to RabbitMQ."""
        try:
            logger.info(f"Connecting to RabbitMQ: {self.rabbitmq_url}")
            self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
            self.channel = await self.connection.channel()
            
            # Set prefetch count for fair dispatch
            await self.channel.set_qos(prefetch_count=1)
            
            # Declare queue (creates if not exists)
            self.queue = await self.channel.declare_queue(
                self.queue_name,
                durable=True,
            )
            
            logger.info(f"Connected to RabbitMQ, queue: {self.queue_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            return False
    
    async def disconnect(self):
        """Close RabbitMQ connection."""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            logger.info("Disconnected from RabbitMQ")
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to RabbitMQ."""
        return (
            self.connection is not None 
            and not self.connection.is_closed
        )
    
    async def start_consuming(self):
        """Start consuming messages from the queue."""
        if not self.is_connected:
            connected = await self.connect()
            if not connected:
                logger.error("Cannot start consuming: not connected to RabbitMQ")
                return
        
        self._running = True
        logger.info(f"Starting to consume messages from {self.queue_name}")
        
        await self.queue.consume(self._process_message)
    
    async def stop_consuming(self):
        """Stop consuming messages."""
        self._running = False
        await self.disconnect()
    
    async def _process_message(self, message: IncomingMessage):
        """Process a single message from the queue."""
        async with message.process():
            try:
                # Parse message body
                body = json.loads(message.body.decode())
                logger.info(f"Received message: {body.get('jobId', 'unknown')}")
                
                # Parse to Pydantic model
                task = ImageTaskMessage(**body)
                
                # Process the task
                await self._handle_task(task)
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in message: {e}")
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                # Don't requeue on processing errors
    
    async def _handle_task(self, task: ImageTaskMessage):
        """Handle an image generation/editing task."""
        image_service = get_image_service()
        callback_service = get_callback_service()
        
        try:
            if task.action == ImageAction.CREATE:
                # Create new character image
                logger.info(f"Creating character image for job {task.job_id}")
                image_url = image_service.create_character_image(task.message)
                
            elif task.action == ImageAction.EDIT:
                # Edit existing image
                if not task.image_url:
                    raise ValueError("image_url is required for edit action")
                
                edit_request = task.edit_request or task.message
                logger.info(f"Editing image for job {task.job_id}")
                image_url = image_service.edit_image(task.image_url, edit_request)
                
            else:
                raise ValueError(f"Unknown action: {task.action}")
            
            # Send success callback
            await callback_service.send_success_callback(
                job_id=task.job_id,
                image_url=image_url,
                character_id=task.character_id,
                callback_url=task.callback_url,
            )
            
            logger.info(f"Task {task.job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Task {task.job_id} failed: {e}")
            
            # Send failure callback
            await callback_service.send_failure_callback(
                job_id=task.job_id,
                error=str(e),
                character_id=task.character_id,
                callback_url=task.callback_url,
            )


# Singleton instance
_image_consumer: Optional[ImageConsumer] = None


def get_image_consumer() -> ImageConsumer:
    """Get or create ImageConsumer singleton."""
    global _image_consumer
    if _image_consumer is None:
        _image_consumer = ImageConsumer()
    return _image_consumer
