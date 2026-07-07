import httpx


def get_user_todos_sync(user_id: int) -> dict:
    response = httpx.get(f"https://dummyjson.com/todos/user/{user_id}?delay=4000")
    return response.json()
