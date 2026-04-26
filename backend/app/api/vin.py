from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import Settings, get_settings
from app.schemas.search import VINSpec
from app.vin.decoder import decode_vin

router = APIRouter(prefix="/vin", tags=["vin"])


@router.get("/{vin}", response_model=VINSpec)
async def get_vin(vin: str, request: Request, settings: Settings = Depends(get_settings)):
    spec = await decode_vin(vin, request.app.state.supabase, settings)
    if spec is None:
        raise HTTPException(status_code=422, detail="VIN could not be decoded")
    return spec
