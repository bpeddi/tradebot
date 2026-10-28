from fastapi import APIRouter, Depends, HTTPException

from web.api.db import get_db
from web.api.deps import create_access_token, get_current_user, hash_password, verify_password
from web.api.schemas import AuthRequest, ChangePasswordRequest

router = APIRouter()


@router.post("/register", status_code=201)
async def register(req: AuthRequest, conn=Depends(get_db)):
    """Bootstrap-only: works once, while no user exists yet. This is a
    single-person tool, so open registration is unnecessary exposure once
    this is reachable from a public IP."""
    existing_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing_count > 0:
        raise HTTPException(status_code=403, detail="Registration is closed — an account already exists")
    conn.execute(
        "INSERT INTO users (username, hashed_pw) VALUES (?, ?)",
        (req.username, hash_password(req.password)),
    )
    conn.commit()
    return {"access_token": create_access_token(req.username), "token_type": "bearer"}


@router.post("/login")
async def login(req: AuthRequest, conn=Depends(get_db)):
    row = conn.execute(
        "SELECT hashed_pw FROM users WHERE username=?", (req.username,)
    ).fetchone()
    if not row or not verify_password(req.password, row[0]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return {"access_token": create_access_token(req.username), "token_type": "bearer"}


@router.get("/me")
async def me(username: str = Depends(get_current_user)):
    return {"username": username}


@router.put("/password")
async def change_password(
    req: ChangePasswordRequest,
    username: str = Depends(get_current_user),
    conn=Depends(get_db),
):
    row = conn.execute("SELECT hashed_pw FROM users WHERE username=?", (username,)).fetchone()
    if not row or not verify_password(req.current_password, row[0]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    conn.execute(
        "UPDATE users SET hashed_pw=? WHERE username=?",
        (hash_password(req.new_password), username),
    )
    conn.commit()
    return {"ok": True}
