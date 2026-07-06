from pydantic import BaseModel, ConfigDict, Field


class DummyJsonUserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    email: str


class DummyJsonTodoResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    todo: str
    completed: bool


class DummyJsonUserTodoResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    todos: list[DummyJsonTodoResponse]
    total: int
