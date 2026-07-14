class EventNotFoundError(Exception):
    pass


class SeatsNotFoundError(Exception):
    pass


class SeatsUnavailableError(Exception):
    pass


class DuplicateSeatError(Exception):
    pass


class PaymentUnavailableError(Exception):
    pass


class AccessDeniedError(Exception):
    pass
