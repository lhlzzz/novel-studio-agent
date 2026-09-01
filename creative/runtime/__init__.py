"""Creative runtime composition root."""

from creative.runtime.state import InvalidStateTransition, apply_block, transition

def get_runtime(*args, **kwargs):
    from creative.runtime.container import get_runtime as _get
    return _get(*args, **kwargs)

__all__ = [
    "InvalidStateTransition",
    "apply_block",
    "get_runtime",
    "transition",
]
