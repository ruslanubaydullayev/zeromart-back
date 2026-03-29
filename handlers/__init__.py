"""Bot routers."""

from handlers.admin import router as admin_router
from handlers.common import router as common_router
from handlers.seller import router as seller_router

__all__ = ["admin_router", "common_router", "seller_router"]
