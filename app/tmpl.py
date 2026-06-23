"""Jinja2 템플릿 인스턴스 — 순환 임포트 방지를 위해 별도 모듈로 분리."""

import json
from pathlib import Path

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["tojson"] = lambda v, indent=None: json.dumps(v, ensure_ascii=False, indent=indent)
