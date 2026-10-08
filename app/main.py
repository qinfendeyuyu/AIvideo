"""Legacy episode studio entry point; the all-local gateway is a separate app.

Run with: python -m uvicorn app.main:app --host 127.0.0.1 --port 8088
For the strict no-cloud workflow use scripts/start_local_free.ps1 instead.
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.api.routes import router, studio_page

app = FastAPI(title="AI 漫剧本地制作系统", version="0.2.0")
app.include_router(router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def studio() -> HTMLResponse:
    return studio_page()
