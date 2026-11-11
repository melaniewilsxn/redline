import pytest

from redline.search.errors import EmptyQueryError
from redline.search.models import SearchMatchMode, SearchPhrase
from redline.search.query_parser import parse_query


def test_unquoted_words_become_terms() -> None:
    """Unquoted words become terms, in order."""
    query = parse_query("alpha beta")

    assert query.terms == ["alpha", "beta"]
    assert query.phrases == []


def test_quoted_words_become_a_phrase() -> None:
    """Two or more quoted words become one phrase."""
    query = parse_query('"written notice"')

    assert query.terms == []
    assert query.phrases == [SearchPhrase(terms=["written", "notice"])]


def test_single_word_in_quotes_becomes_a_term() -> None:
    """A quoted part with one word is an unquoted term."""
    query = parse_query('"hello"')

    assert query.terms == ["hello"]
    assert query.phrases == []


def test_duplicate_terms_are_removed_in_order() -> None:
    """A repeated term is kept once, at its first position."""
    query = parse_query("beta alpha beta")

    assert query.terms == ["beta", "alpha"]


def test_unmatched_quote_is_ignored() -> None:
    """An unmatched quote is ignored, and the words around it stay terms."""
    query = parse_query('say "hello')

    assert query.terms == ["say", "hello"]
    assert query.phrases == []


def test_query_with_no_words_raises_empty_query_error() -> None:
    """A query with no words raises EmptyQueryError."""
    with pytest.raises(EmptyQueryError):
        parse_query('"???"')


def test_query_terms_are_normalized_like_document_terms() -> None:
    """A possessive in the query is folded the same way as in a document."""
    query = parse_query("Company's")

    assert query.terms == ["company"]


def test_prefix_mode_moves_the_last_unquoted_term_to_prefix_terms() -> None:
    """The last word being typed is a prefix, and the earlier words stay exact."""
    query = parse_query("written indemn", SearchMatchMode.PREFIX)

    assert query.terms == ["written"]
    assert query.prefix_terms == ["indemn"]
    assert query.phrases == []


def test_prefix_mode_keeps_the_last_term_exact_after_trailing_whitespace() -> None:
    """A finished word, followed by a space, stays an exact term."""
    query = parse_query("written indemn ", SearchMatchMode.PREFIX)

    assert query.terms == ["written", "indemn"]
    assert query.prefix_terms == []


def test_prefix_mode_leaves_a_trailing_quoted_phrase_exact() -> None:
    """A query that ends in a closing quote does not turn that phrase into a prefix."""
    query = parse_query('indemn "written notice"', SearchMatchMode.PREFIX)

    assert query.terms == ["indemn"]
    assert query.phrases == [SearchPhrase(terms=["written", "notice"])]
    assert query.prefix_terms == []


def test_exact_mode_never_produces_prefix_terms() -> None:
    """Exact mode keeps every word as a whole term."""
    query = parse_query("written indemn")

    assert query.terms == ["written", "indemn"]
    assert query.prefix_terms == []


def test_prefix_only_query_is_not_empty() -> None:
    """A single unfinished word is a prefix query, not an empty one."""
    query = parse_query("Mas", SearchMatchMode.PREFIX)

    assert query.terms == []
    assert query.prefix_terms == ["mas"]
