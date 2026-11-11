import re

from redline.search.errors import EmptyQueryError
from redline.search.models import SearchMatchMode, SearchPhrase, SearchQuery
from redline.search.tokenizer import tokenize

PHRASE_PATTERN = re.compile(r'"([^"]*)"')
MAXIMUM_QUERY_CHARACTERS = 500
MINIMUM_PHRASE_TERMS = 2


def parse_query(
    query_text: str, match_mode: SearchMatchMode = SearchMatchMode.EXACT
) -> SearchQuery:
    """Turn query text into terms, phrases, and one prefix term.
    A query with no words is an error."""
    terms: list[str] = []
    seen: set[str] = set()
    phrases: list[SearchPhrase] = []
    cursor = 0
    for match in PHRASE_PATTERN.finditer(query_text):
        append_terms(terms, seen, query_text[cursor : match.start()])
        quoted_terms = [token.term for token in tokenize(match.group(1))]
        if len(quoted_terms) >= MINIMUM_PHRASE_TERMS:
            phrases.append(SearchPhrase(terms=quoted_terms))
        elif len(quoted_terms) == 1:
            append_term(terms, seen, quoted_terms[0])
        cursor = match.end()
    append_terms(terms, seen, query_text[cursor:])
    prefix_terms = take_prefix_term(query_text, match_mode, terms)
    if prefix_terms:
        terms = terms[:-1]
    if not terms and not phrases and not prefix_terms:
        raise EmptyQueryError()
    return SearchQuery(terms=terms, phrases=phrases, prefix_terms=prefix_terms)


def take_prefix_term(query_text: str, match_mode: SearchMatchMode, terms: list[str]) -> list[str]:
    """Return the last word when it is still being typed. Otherwise return nothing."""
    if (
        match_mode != SearchMatchMode.PREFIX
        or not terms
        or not query_ends_inside_a_term(query_text)
    ):
        return []
    return [terms[-1]]


def query_ends_inside_a_term(query_text: str) -> bool:
    """Return whether the query ends mid-word, rather than after a space or a closing quote."""
    if query_text == "":
        return False
    last_character = query_text[-1]
    return not last_character.isspace() and last_character != '"'


def append_terms(terms: list[str], seen: set[str], text: str) -> None:
    """Append each word in text, skipping words already recorded."""
    for token in tokenize(text):
        append_term(terms, seen, token.term)


def append_term(terms: list[str], seen: set[str], term: str) -> None:
    """Append term unless it was already seen."""
    if term in seen:
        return
    seen.add(term)
    terms.append(term)
