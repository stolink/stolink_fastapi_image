# FastAPI Application Entry Point
# StoLink Image Worker - AWS Bedrock based image generation/editing service

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import router
from app.consumers import get_image_consumer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()
    logger.info(f"Starting {settings.app_name}...")
    
    # Start RabbitMQ consumer
    consumer = get_image_consumer()
    try:
        connected = await consumer.connect()
        if connected:
            # Start consuming in background
            asyncio.create_task(consumer.start_consuming())
            logger.info("RabbitMQ consumer started")
        else:
            logger.warning("Failed to connect to RabbitMQ, running without queue consumer")
    except Exception as e:
        logger.error(f"Error starting RabbitMQ consumer: {e}")
    
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down...")
    await consumer.stop_consuming()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="StoLink Image Worker",
    description="AWS Bedrock based image generation and editing service for StoLink",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "StoLink Image Worker",
        "version": "1.0.0",
        "status": "running",
    }
