from ..dummyjson import schemas as dummyjson_schemas
from .schemas import User, Todos, TodoItem, Result


def to_user(response: dummyjson_schemas.DummyJsonUserResponse) -> User:
    return User(
        user_id=response.id,
        user_name=f"{response.first_name} {response.last_name}",
        email=response.email,
    )


def to_todos(response: dummyjson_schemas.DummyJsonUserTodoResponse) -> Todos:
    completed = sum(t.completed for t in response.todos)
    todo_items: list[TodoItem] = [
        TodoItem(id=t.id, todo=t.todo, completed=t.completed) for t in response.todos
    ]

    return Todos(total=response.total, completed=completed, items=todo_items)


def to_result(user: User, todos: Todos) -> Result:
    return Result(user=user, todos=todos)
