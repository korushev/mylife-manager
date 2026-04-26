from fastapi import APIRouter

from backend.app.schemas import StubCapabilityOut

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/capabilities", response_model=StubCapabilityOut)
def ai_capabilities() -> StubCapabilityOut:
    return StubCapabilityOut(
        module="ai",
        status="coming_soon",
        message="AI extraction/categorization is planned in the next iteration.",
    )
