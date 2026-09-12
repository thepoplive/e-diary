from pathlib import Path

from fastapi.templating import Jinja2Templates

from .helpers import fmt_date

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["fmt_date"] = fmt_date


def render(name: str, context: dict | None = None, status_code: int = 200):
    """Отрисовка шаблона с учётом новой сигнатуры Starlette."""
    if context is None:
        context = {}
    context.setdefault("request", None)
    request = context["request"]
    return templates.TemplateResponse(request, name, context, status_code=status_code)