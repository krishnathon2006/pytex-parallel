"""Custom exceptions for report building failures."""


class ReportBuildError(Exception):
    """Base exception for report build errors."""

    public_message = "Failed to build report"

    def __init__(self):
        super().__init__(self.public_message)


class UserNotFoundError(ReportBuildError):
    """Raised when a requested user cannot be found."""

    public_message = "User not found"


class ReportProviderError(ReportBuildError):
    """Raised when report data cannot be retrieved from the provider."""

    public_message = "Unable to retrieve report data"
