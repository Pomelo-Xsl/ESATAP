from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import devices, pages, tests
from app.core.config import BASE_DIR, settings
from app.core.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
app.include_router(devices.router)
app.include_router(tests.router)
app.include_router(pages.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": settings.version}
