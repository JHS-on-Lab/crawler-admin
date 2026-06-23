"""로그인 / 로그아웃."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app import config
from app.tmpl import templates

router = APIRouter()


@router.get("/login")
async def login_page(request: Request):
    if request.session.get("authenticated"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if username == config.ADMIN_USER and password == config.ADMIN_PASSWORD:
        request.session["authenticated"] = True
        request.session["user"] = username
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "아이디 또는 비밀번호가 올바르지 않습니다."},
        status_code=401,
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
