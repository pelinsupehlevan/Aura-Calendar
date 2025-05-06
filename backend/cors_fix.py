from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable

def add_cors_middleware(app: FastAPI) -> None:
    """Safely add CORS middleware to a FastAPI app"""

    # Just add CORS middleware (FastAPI will handle deduplication if needed)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=86400,
    )

    class EnsureCORSMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Callable) -> Response:
            if request.method == "OPTIONS":
                response = Response()
                response.headers["Access-Control-Allow-Origin"] = "*"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept"
                response.headers["Access-Control-Max-Age"] = "86400"
                return response

            response = await call_next(request)
            response.headers["Access-Control-Allow-Origin"] = "*"
            return response

    app.add_middleware(EnsureCORSMiddleware)
