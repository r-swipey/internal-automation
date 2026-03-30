from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import auth, contractors, timesheets, notes

app = FastAPI(
    title="Ben's Contractor Payment API",
    description="Contractor payment automation for Ben's Cloud Kitchen × Swipey",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(contractors.router)
app.include_router(timesheets.router)
app.include_router(notes.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "bens-contractor-payment"}
