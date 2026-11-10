import re

from redline.search.errors import EmptyQueryError
from redline.search.models import SearchPhrase, SearchQuery
from redline.search.tokenizer import tokenize

PHRASE_PATTERN = re.compile(r'"([^"]*)"')
MAXIMUM_QUERY_CHARACTERS = 500
MINIMUM_PHRASE_TERMS = 2


def parse_query(query_text: str) -> SearchQuery:
    """Turn query text into terms and phrases. A query with no words is an error."""
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
    if not terms and not phrases:
        raise EmptyQueryError()
    return SearchQuery(terms=terms, phrases=phrases)


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
