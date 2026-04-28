"""
Open-Claw custom exceptions.
"""


class OpenClawError(Exception):
    """Base exception for Open-Claw."""


class CoreMemoryProtectedError(OpenClawError):
    """
    Raised when any operation attempts to write to vault/core/.
    This is a hard safety boundary — core memory is NEVER modified
    by ingestion, reflection, or linking.
    """


class DuplicateMemoryError(OpenClawError):
    """Raised when a duplicate memory is detected."""


class InvalidMemoryError(OpenClawError):
    """Raised when a memory structure is invalid."""
