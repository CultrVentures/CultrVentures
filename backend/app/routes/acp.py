"""
ACP (Agent Commerce Protocol) endpoints.
Bridges Virtuals Protocol on-chain ACP and OpenAI/Stripe consumer ACP.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/acp")


class OfferingResponse(BaseModel):
    id: str
    name: str
    description: str
    price_usdc: float | None = None
    stripe_price_id: str | None = None
    category: str


@router.get("/offerings")
async def list_offerings():
    """List all agent service offerings (on-chain + consumer)."""
    # TODO: Aggregate from ACP runtime + Stripe catalog
    return {"offerings": [], "total": 0}


@router.post("/purchase")
async def purchase_offering(offering_id: str, payment_method: str = "stripe"):
    """
    Purchase an agent service offering.
    payment_method: stripe | virtuals_acp
    """
    # TODO: Route to Stripe or Virtuals ACP based on payment method
    return {
        "offering_id": offering_id,
        "status": "not_implemented",
        "payment_method": payment_method,
    }


@router.get("/transactions")
async def list_transactions(limit: int = 20):
    """List recent ACP transactions."""
    return {"transactions": [], "total": 0}
