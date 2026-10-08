from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.certificates import router
from app.config import CERT_DIR
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Bulk Certificate Generator", version="1.0.0", lifespan=lifespan)
app.include_router(router)
