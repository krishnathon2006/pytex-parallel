import httpx
from fastapi import Request


def get_dummyjson_client(request: Request) -> httpx.AsyncClient:
    """Returns the dummyjson client from the request state."""
    return request.app.state.dummyjson_client
