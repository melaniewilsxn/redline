import re

from redline.editing.models import TextSpan
from redline.search.models import Token

WORD_PATTERN = re.compile(r"\w+(?:[-'’]\w+)*")  # noqa: RUF001
POSSESSIVE_SUFFIXES = ("'s", "’s")  # noqa: RUF001


def tokenize(text: str) -> list[Token]:
    """Return every word in text, in order, with the span of the original match."""
    tokens: list[Token] = []
    for match in WORD_PATTERN.finditer(text):
        tokens.append(
            Token(
                term=normalize_term(match.group()),
                span=TextSpan(start=match.start(), end=match.end()),
            )
        )
    return tokens


def normalize_term(word: str) -> str:
    """Return the word folded to one case, without one trailing possessive."""
    folded = word.casefold()
    for suffix in POSSESSIVE_SUFFIXES:
        if folded.endswith(suffix):
            return folded[: -len(suffix)]
    return folded
