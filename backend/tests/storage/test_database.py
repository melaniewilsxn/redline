from redline.storage.database import get_safe_error_detail

NORMAL_ERROR_MESSAGE = "pool closed"


def test_get_safe_error_detail_returns_a_normal_message() -> None:
    """A message without a connection string is returned as itself."""
    detail = get_safe_error_detail(RuntimeError(NORMAL_ERROR_MESSAGE))

    assert detail == NORMAL_ERROR_MESSAGE


def test_get_safe_error_detail_hides_connection_strings() -> None:
    """A message that contains a URL is replaced with the exception type."""
    error = RuntimeError("failed postgresql://redline:secret@localhost/redline")

    detail = get_safe_error_detail(error)

    assert detail == type(error).__name__


def test_get_safe_error_detail_hides_passwords() -> None:
    """A message that mentions a password is replaced with the exception type."""
    error = RuntimeError("password authentication failed")

    detail = get_safe_error_detail(error)

    assert detail == type(error).__name__
