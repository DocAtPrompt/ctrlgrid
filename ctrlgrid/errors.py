"""The one exception type the user is ever meant to see.

§ 12 calls error messages "the face of the tool" and means it: an error that
does not let the user act is a bug. Two things make a message actionable, and
both are carried here rather than reconstructed at the top level — the **field
path** the value came from, and the **line** of the definition file it was
written on (§ 13, the reason for `ruamel.yaml`).

Values are always reported in the unit the user wrote (§ 3.3), so the raw text
travels with the value and ends up here unchanged.
"""

from __future__ import annotations


class CtrlGridError(Exception):
    """Base class, so a caller can catch everything the tool raises deliberately."""


class DefinitionError(CtrlGridError):
    """The definition file says something the tool cannot act on.

    `field` is the dotted path into the definition ("families.0.base_spacing"),
    `line` the line in the source file. Both are optional because a value can
    also arrive from the command line, where neither exists.
    """

    def __init__(self, message: str, *, field: str | None = None, line: int | None = None):
        self.message = message
        self.field = field
        self.line = line
        super().__init__(self._format())

    def _format(self) -> str:
        where = ", ".join(
            part
            for part in (
                f"line {self.line}" if self.line is not None else None,
                self.field,
            )
            if part
        )
        return f"{where}: {self.message}" if where else self.message

    def at(self, *, field: str | None = None, line: int | None = None) -> DefinitionError:
        """Return the same error with location details filled in.

        A parser deep in the call stack knows what is wrong but not always
        where it came from; the caller that does can add it without the
        message being rebuilt from strings.
        """
        return DefinitionError(
            self.message,
            field=self.field if field is None else field,
            line=self.line if line is None else line,
        )
