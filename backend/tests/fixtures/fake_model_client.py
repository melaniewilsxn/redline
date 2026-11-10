from redline.ai.models import RedlineSuggestion


class FakeModelClient:
    """Returns fixed suggestions and records the last prompts."""

    def __init__(self, suggestions: list[RedlineSuggestion]) -> None:
        """Store the suggestions this client will return."""
        self.suggestions = suggestions
        self.system_prompt = ""
        self.user_prompt = ""

    def request_suggestions(self, system_prompt: str, user_prompt: str) -> list[RedlineSuggestion]:
        """Record the prompts and return the fixed suggestions."""
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.suggestions


class FailingModelClient:
    """Raises a fixed error from every request."""

    def __init__(self, error: Exception) -> None:
        """Store the error this client will raise."""
        self.error = error

    def request_suggestions(self, system_prompt: str, user_prompt: str) -> list[RedlineSuggestion]:
        """Raise the stored error."""
        raise self.error
