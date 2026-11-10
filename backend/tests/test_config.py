import pytest

from redline.config import read_environment_variable
from redline.logging_setup import configure_logging

PRESENT_VARIABLE = "REDLINE_TEST_SETTING"
PRESENT_VALUE = "present"
UNKNOWN_LOG_LEVEL = "NOPE"


def test_read_environment_variable_returns_a_present_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """A variable that is set is returned."""
    monkeypatch.setenv(PRESENT_VARIABLE, PRESENT_VALUE)

    value = read_environment_variable(PRESENT_VARIABLE)

    assert value == PRESENT_VALUE


def test_read_environment_variable_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A variable that is unset raises."""
    monkeypatch.delenv(PRESENT_VARIABLE, raising=False)

    with pytest.raises(RuntimeError):
        read_environment_variable(PRESENT_VARIABLE)


def test_configure_logging_rejects_an_unknown_level() -> None:
    """An unknown log level names the setting and raises."""
    with pytest.raises(RuntimeError):
        configure_logging(UNKNOWN_LOG_LEVEL)
