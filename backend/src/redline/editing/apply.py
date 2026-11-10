import logging

from redline.editing.anchors import resolve_change
from redline.editing.errors import OverlappingChangesError
from redline.editing.models import AppliedEdit, Change, EditedText, ResolvedChange

logger = logging.getLogger(__name__)


def apply_changes(text: str, changes: list[Change]) -> EditedText:
    """Resolve every change, reject overlaps, and rebuild the text once."""
    logger.info(f"Started applying {len(changes)} changes to a document of {len(text)} characters")
    resolved = [
        resolve_change(text, change, change_index) for change_index, change in enumerate(changes)
    ]
    sorted_changes = sorted(resolved, key=lambda change: (change.span.start, change.span.end))
    raise_on_overlapping_changes(sorted_changes)
    edited_text = rebuild_text(text, sorted_changes)
    applied_edits = [
        AppliedEdit(span=change.span, replacement_length=len(change.replacement))
        for change in sorted_changes
    ]
    logger.info(
        f"Finished applying {len(applied_edits)} edits, new document length {len(edited_text)}"
    )
    return EditedText(text=edited_text, applied_edits=applied_edits)


def raise_on_overlapping_changes(sorted_changes: list[ResolvedChange]) -> None:
    """Raise when two neighboring changes overlap."""
    for index in range(1, len(sorted_changes)):
        previous = sorted_changes[index - 1]
        current = sorted_changes[index]
        same_insert_position = (
            previous.span.start == previous.span.end
            and current.span.start == current.span.end
            and previous.span.start == current.span.start
        )
        if current.span.start < previous.span.end or same_insert_position:
            logger.warning(
                f"Rejected overlapping changes {previous.change_index} and {current.change_index}"
            )
            raise OverlappingChangesError(previous.change_index, current.change_index)


def rebuild_text(text: str, sorted_changes: list[ResolvedChange]) -> str:
    """Join the untouched slices and the replacements in one pass."""
    pieces: list[str] = []
    cursor = 0
    for change in sorted_changes:
        pieces.append(text[cursor : change.span.start])
        pieces.append(change.replacement)
        cursor = change.span.end
    pieces.append(text[cursor:])
    return "".join(pieces)
