from fastapi import APIRouter, HTTPException, status, Depends
from app.core.database import get_db
from app.core.auth import hash_password, verify_password, create_access_token, require_manager, require_admin
from app.core.config import settings
from app.schemas.schemas import LoginRequest, SetupAdminRequest, TokenResponse, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    db = get_db()
    result = db.table("users").select("*").eq("email", body.email).eq("is_active", True).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user = result.data[0]
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": user["id"], "email": user["email"], "role": user["role"]})
    return TokenResponse(access_token=token, user_id=user["id"], name=user["name"], role=user["role"])


@router.post("/setup-admin", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def setup_admin(body: SetupAdminRequest):
    if settings.environment != "development":
        raise HTTPException(status_code=404, detail="Not found")
    db = get_db()
    existing = db.table("users").select("id").limit(1).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Admin already exists. This endpoint is disabled.")

    hashed = hash_password(body.password)
    result = db.table("users").insert({
        "email": body.email,
        "password_hash": hashed,
        "name": body.name,
        "role": "admin",
    }).execute()

    user = result.data[0]
    token = create_access_token({"sub": user["id"], "email": user["email"], "role": user["role"]})
    return TokenResponse(access_token=token, user_id=user["id"], name=user["name"], role=user["role"])


@router.get("/me")
async def me(user: dict = Depends(require_manager)):
    return user


@router.get("/users", response_model=list[UserOut])
async def list_users(user=Depends(require_admin)):
    db = get_db()
    result = db.table("users") \
        .select("id, email, name, role, is_active, created_at") \
        .order("created_at", desc=False).execute()
    return result.data


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, user=Depends(require_admin)):
    db = get_db()
    if body.role not in ("admin", "manager"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'manager'")
    existing = db.table("users").select("id").eq("email", body.email).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="A user with this email already exists")
    result = db.table("users").insert({
        "email": body.email,
        "password_hash": hash_password(body.password),
        "name": body.name,
        "role": body.role,
    }).execute()
    return result.data[0]


@router.delete("/users/{user_id}/deactivate", status_code=204)
async def deactivate_user(user_id: str, user=Depends(require_admin)):
    db = get_db()
    if user["sub"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    result = db.table("users").update({"is_active": False}).eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
