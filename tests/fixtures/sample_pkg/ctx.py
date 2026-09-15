from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import App  # deliberate cycle, guarded — should not count as a real cycle later


class CtxThing:
    pass
