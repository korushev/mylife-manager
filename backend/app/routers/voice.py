from fastapi import APIRouter

from backend.app.schemas import StubCapabilityOut

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.get("/capabilities", response_model=StubCapabilityOut)
def voice_capabilities() -> StubCapabilityOut:
    return StubCapabilityOut(
        module="voice",
        status="coming_soon",
        message="Speech-to-text and text-to-speech will be added after MVP.",
    )
