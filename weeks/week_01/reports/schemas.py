from pydantic import BaseModel
from .entities import JobStatus


class User(BaseModel):
    user_id: int
    user_name: str
    email: str


class TodoItem(BaseModel):
    id: int
    todo: str
    completed: bool


class Todos(BaseModel):
    total: int
    completed: int
    items: list[TodoItem]


class Result(BaseModel):
    user: User
    todos: Todos


# {
#   "job_id": "some-unique-id",
#   "status": "done",
#   "result": {
#     "user": {
#       "user_id": 1,
#       "user_name": "Emily",
#       "email": "emily.johnson@x.dummyjson.com"
#     },
#     "todos": {
#       "total": 2,
#       "completed": 1,
#       "items": [
#         {
#           "id": 1,
#           "todo": "Do something nice for someone you care about",
#           "completed": false
#         },
#         {
#           "id": 2,
#           "todo": "Memorize a poem",
#           "completed": true
#         }
#       ]
#     }
#   }
# }
class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    result: Result | None = None
    error: str | None = None
