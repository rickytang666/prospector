import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from discord_bot.bot import start_bot
from internal_context.router import router as ic_router
# from retrieval.router import router as retrieval_router
# from scraper.router import router as scraper_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(start_bot())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)

app.include_router(ic_router, prefix="/internal")
# app.include_router(retrieval_router, prefix="/retrieval")
# app.include_router(scraper_router, prefix="/scraper")
