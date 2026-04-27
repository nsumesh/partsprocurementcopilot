from fastapi import APIRouter, HTTPException, Request

from app.db.supabase import fetch_vendors_for_part
from app.schemas.procurement import VendorPart

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("/part/{part_id}", response_model=list[VendorPart])
async def get_vendors_for_part(part_id: str, request: Request):
    rows = await fetch_vendors_for_part(request.app.state.supabase, part_id)
    if not rows:
        raise HTTPException(status_code=404, detail="No vendors found for this part")
    return [VendorPart(**r) for r in rows]
