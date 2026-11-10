from redline.editing.models import AppliedEdit, LiveSpan, RebasedSpan, StaleSpan, TextSpan


def rebase_span(span: TextSpan, applied_edits: list[AppliedEdit]) -> RebasedSpan:
    """Move a span through applied edits, or mark it stale when an edit changes its text."""
    shift = 0
    for edit in applied_edits:
        if edit.span.end <= span.start:
            shift += edit.length_change
        elif edit.span.start >= span.end:
            continue
        else:
            return StaleSpan(conflicting_edit=edit)
    return LiveSpan(span=TextSpan(start=span.start + shift, end=span.end + shift))
