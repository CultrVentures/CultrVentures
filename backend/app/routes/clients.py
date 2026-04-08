"""
Client management endpoints — CRUD for consulting clients.
Client data persists in both PostgreSQL (structured) and vault (agent-readable).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/clients")


class ClientCreate(BaseModel):
    name: str
    company: str
    email: str
    tier: str = "starter"  # starter | growth | enterprise
    industry: str | None = None


class ClientResponse(BaseModel):
    id: str
    name: str
    company: str
    email: str
    tier: str
    industry: str | None
    created_at: str


@router.get("/")
async def list_clients():
    """List all clients (RLS-filtered by auth context)."""
    # TODO: Query from DB with RLS
    return {"clients": [], "total": 0}


@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(req: ClientCreate):
    """Create a new client — writes to DB + vault/clients/{slug}/."""
    # TODO: Insert to DB, create vault directory
    raise HTTPException(status_code=501, detail="Not yet implemented")


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: str):
    """Get a specific client's profile."""
    raise HTTPException(status_code=404, detail=f"Client {client_id} not found")


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(client_id: str, req: ClientCreate):
    """Update client info — syncs to vault."""
    raise HTTPException(status_code=501, detail="Not yet implemented")
