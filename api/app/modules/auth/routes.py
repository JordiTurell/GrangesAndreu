from fastapi import APIRouter

from .controllers import router as auth_controller

router = APIRouter(prefix="/auth", tags=["auth"])
router.include_router(auth_controller)