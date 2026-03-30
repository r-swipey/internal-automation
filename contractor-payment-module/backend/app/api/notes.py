from fastapi import APIRouter, HTTPException, Depends
from app.core.database import get_db
from app.core.auth import require_manager
from app.schemas.schemas import NoteCreate, NoteUpdate, NoteOut

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("/contractor/{contractor_id}", response_model=list[NoteOut])
async def list_notes(contractor_id: str, user=Depends(require_manager)):
    db = get_db()
    result = db.table("notes").select("*").eq("contractor_id", contractor_id).order("created_at", desc=True).execute()
    return result.data


@router.get("/contractor/{contractor_id}/external", response_model=list[NoteOut])
async def list_external_notes(contractor_id: str, user=Depends(require_manager)):
    db = get_db()
    result = db.table("notes").select("*").eq("contractor_id", contractor_id).eq("visibility", "external").order("created_at", desc=True).execute()
    return result.data


@router.get("/token/{token}/external", response_model=list[NoteOut])
async def list_external_notes_by_token(token: str):
    db = get_db()
    contractor_result = db.table("contractors").select("id").eq("registration_token", token).execute()
    if not contractor_result.data:
        raise HTTPException(status_code=404, detail="Invalid token")

    contractor_id = contractor_result.data[0]["id"]
    result = db.table("notes").select("*").eq("contractor_id", contractor_id).eq("visibility", "external").order("created_at", desc=True).execute()
    return result.data


@router.post("", response_model=NoteOut, status_code=201)
async def create_note(body: NoteCreate, user=Depends(require_manager)):
    db = get_db()
    if body.visibility not in ("internal", "external"):
        raise HTTPException(status_code=400, detail="visibility must be 'internal' or 'external'")
    result = db.table("notes").insert({
        "contractor_id": body.contractor_id,
        "content": body.content,
        "visibility": body.visibility,
        "created_by": user["sub"],
    }).execute()
    return result.data[0]


@router.patch("/{note_id}", response_model=NoteOut)
async def update_note(note_id: str, body: NoteUpdate, user=Depends(require_manager)):
    db = get_db()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = db.table("notes").update(updates).eq("id", note_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Note not found")
    return result.data[0]


@router.delete("/{note_id}")
async def delete_note(note_id: str, user=Depends(require_manager)):
    db = get_db()
    result = db.table("notes").delete().eq("id", note_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}
