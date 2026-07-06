class DummyJsonError(Exception):
    pass


class DummyJsonUserNotFoundError(DummyJsonError):
    pass


class DummyJsonInvalidResponseError(DummyJsonError):
    pass
