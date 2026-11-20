"""Exception hierarchy shared by the library and the CLI."""

from __future__ import annotations


class ZodiacError(ValueError):
    """Base class for all zodiac domain errors."""


class InvalidDateError(ZodiacError):
    """Raised when a date does not exist or is malformed."""


class OutOfRangeError(ZodiacError):
    """Raised when a date falls outside the supported calendar range."""