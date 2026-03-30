import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from .api.routes import router
from .jobs.manager import JobManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_manager = JobManager()
    app.state.job_manager = job_manager
    job_manager.start()
    yield
    await job_manager.stop()


app = FastAPI(title="VirtualDreams", lifespan=lifespan)
app.include_router(router)


def run() -> None:
    load_dotenv()
    uvicorn.run(
        "virtualdreams.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
