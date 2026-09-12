import logging
import os
import secrets
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .database import init_db
from . import database
from . import models
from .auth import hash_password
from .routers import admin, auth, parent, student, teacher


def _configure_windows_console() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
        try:
            os.system("chcp 65001 > nul")
        except Exception:  # noqa: BLE001
            pass


_configure_windows_console()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("diary")


def ensure_initial_data():
    """Создаёт главного администратора и настройки при первом запуске."""
    db = database.SessionLocal()
    try:
        admin = db.query(models.User).filter(models.User.role == "admin").first()
        if not admin:
            password = secrets.token_urlsafe(8)
            login = "admin"
            admin = models.User(
                login=login,
                password_hash=hash_password(password),
                full_name="Главный администратор",
                phone="",
                role="admin",
                setup_done=False,
            )
            db.add(admin)
            db.commit()
            logger.info("=" * 55)
            logger.info("Создан аккаунт ГЛАВНОГО АДМИНИСТРАТОРА")
            logger.info("  Логин:    %s", login)
            logger.info("  Пароль:   %s", password)
            logger.info("  Ссылка:   http://localhost:8000/login")
            logger.info("=" * 55)

        if not db.query(models.Settings).first():
            db.add(models.Settings(id=1))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    models.Base.metadata.create_all(bind=database.SessionLocal().bind)
    ensure_initial_data()
    yield


app = FastAPI(title="Электронный дневник", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(teacher.router)
app.include_router(parent.router)
app.include_router(student.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse("/login", status_code=302)
    if exc.status_code == 403:
        return RedirectResponse("/login", status_code=302)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)