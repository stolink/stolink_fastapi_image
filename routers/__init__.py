# routers 패키지 초기화

from .upload import router as upload_router
from .ai import router as ai_router

__all__ = ["upload_router", "ai_router"]
