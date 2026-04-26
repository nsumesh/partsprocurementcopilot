from fastapi import APIRouter, Request

from app.db.supabase import fetch_orders, insert_order
from app.schemas.orders import Order, OrderCreate

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=Order, status_code=201)
async def create_order(body: OrderCreate, request: Request):
    record = await insert_order(request.app.state.supabase, body.model_dump())
    return Order(**record)


@router.get("", response_model=list[Order])
async def list_orders(request: Request):
    rows = await fetch_orders(request.app.state.supabase)
    return [Order(**r) for r in rows]
