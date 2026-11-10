from redline.search.tokenizer import tokenize


def test_tokens_are_case_folded() -> None:
    """Words are folded to one case."""
    tokens = tokenize("Hello WORLD")

    assert [token.term for token in tokens] == ["hello", "world"]


def test_token_spans_cover_the_original_word() -> None:
    """Each span covers the word as it appears in the text."""
    text = "Hello World"

    tokens = tokenize(text)

    assert text[tokens[0].span.start : tokens[0].span.end] == "Hello"
    assert text[tokens[1].span.start : tokens[1].span.end] == "World"


def test_possessive_is_dropped_from_term_but_kept_in_span() -> None:
    """A trailing 's is dropped from the term and kept in the span."""
    text = "Company's"

    tokens = tokenize(text)

    assert tokens[0].term == "company"
    assert text[tokens[0].span.start : tokens[0].span.end] == "Company's"


def test_curly_possessive_is_dropped() -> None:
    """A curly apostrophe possessive is dropped the same way."""
    text = "Company’s"  # noqa: RUF001

    tokens = tokenize(text)

    assert tokens[0].term == "company"
    assert text[tokens[0].span.start : tokens[0].span.end] == "Company’s"  # noqa: RUF001


def test_hyphenated_word_is_one_token() -> None:
    """A hyphenated word stays one token."""
    tokens = tokenize("non-disclosure")

    assert [token.term for token in tokens] == ["non-disclosure"]


def test_punctuation_splits_tokens() -> None:
    """Parentheses are not part of the word."""
    tokens = tokenize("(30)")

    assert [token.term for token in tokens] == ["30"]


def test_word_without_possessive_is_unchanged() -> None:
    """A word that merely ends in s is left as it is."""
    tokens = tokenize("companies")

    assert [token.term for token in tokens] == ["companies"]
