from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from .routes import sessions as sessions_routes
from .routes import workbooks as workbooks_routes


def create_app() -> FastAPI:
    app = FastAPI(title="AIRR POC API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(workbooks_routes.router)
    app.include_router(sessions_routes.router)

    @app.get("/")
    async def root():
        return {"status": "ok"}

    return app


app = create_app()

