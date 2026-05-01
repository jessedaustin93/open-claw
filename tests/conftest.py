"""Pytest configuration for aeon-v1 test suite."""
import pytest
from aeon_v1.bus import MessageBus


@pytest.fixture(autouse=True)
def reset_message_bus():
    """Reset the MessageBus singleton between tests.

    Prevents handler accumulation from agents created in one test
    from leaking into subsequent tests.
    """
    MessageBus.reset()
    yield
    MessageBus.reset()
