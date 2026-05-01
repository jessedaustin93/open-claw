"""Designated write agent for Aeon-V1.

DataWriteAgent is the SOLE component authorized to write to the memory
system within an agent execution context. All other agents must request
writes through the message bus — direct calls to ingest(), reflect(),
simulate_action(), evaluate_simulation(), or select_next_task() from
within an agent run are blocked by the write guard and raise
WriteAuthorizationError.

Bus topics handled
------------------
    data.write.ingest       payload: {text, source}
    data.write.reflect      payload: {}
    data.write.simulate     payload: {task}
    data.write.evaluate     payload: {simulation, result_text}
    data.write.select_task  payload: {}

The agent is instantiated by the Orchestrator on startup and lives for
the duration of the orchestrator's lifetime. Call close() to cleanly
unsubscribe from all topics.
"""
from typing import Dict, Optional

from .bus import get_bus
from .config import Config
from .decision import select_next_task
from .evaluate import evaluate_simulation
from .ingest import ingest
from .reflect import reflect
from .simulate import simulate_action
from .write_guard import write_authorized_context

_WRITE_TOPICS = (
    "data.write.ingest",
    "data.write.reflect",
    "data.write.simulate",
    "data.write.evaluate",
    "data.write.select_task",
)


class DataWriteAgent:
    """Sole authorized writer for the Aeon-V1 memory system.

    Subscribes to all write topics on the message bus. Every handler
    enters write_authorized_context() before calling any write function,
    which satisfies the write guard enforced by write_guard.py.

    Args:
        config: Config instance shared with the Orchestrator.
    """

    def __init__(self, config: Optional[Config] = None) -> None:
        self._config = config or Config()
        bus = get_bus()
        bus.subscribe("data.write.ingest",      self._handle_ingest)
        bus.subscribe("data.write.reflect",     self._handle_reflect)
        bus.subscribe("data.write.simulate",    self._handle_simulate)
        bus.subscribe("data.write.evaluate",    self._handle_evaluate)
        bus.subscribe("data.write.select_task", self._handle_select_task)

    def close(self) -> None:
        """Unsubscribe from all write topics — call when the orchestrator shuts down."""
        bus = get_bus()
        bus.unsubscribe("data.write.ingest",      self._handle_ingest)
        bus.unsubscribe("data.write.reflect",     self._handle_reflect)
        bus.unsubscribe("data.write.simulate",    self._handle_simulate)
        bus.unsubscribe("data.write.evaluate",    self._handle_evaluate)
        bus.unsubscribe("data.write.select_task", self._handle_select_task)

    # ------------------------------------------------------------------ handlers

    def _handle_ingest(self, message: Dict) -> Dict:
        payload = message.get("payload", {})
        with write_authorized_context():
            return ingest(
                text=payload.get("text", ""),
                source=payload.get("source", "agent"),
                config=self._config,
            )

    def _handle_reflect(self, message: Dict) -> Dict:
        with write_authorized_context():
            return reflect(config=self._config)

    def _handle_simulate(self, message: Dict) -> Dict:
        payload = message.get("payload", {})
        task = payload.get("task")
        if task is None:
            return {"simulation": None, "error": "no task in payload"}
        with write_authorized_context():
            return simulate_action(task, config=self._config)

    def _handle_evaluate(self, message: Dict) -> Dict:
        payload = message.get("payload", {})
        simulation = payload.get("simulation")
        result_text = payload.get("result_text", "")
        if simulation is None:
            return {"error": "no simulation in payload"}
        with write_authorized_context():
            return evaluate_simulation(simulation, result_text, config=self._config)

    def _handle_select_task(self, message: Dict) -> Dict:
        with write_authorized_context():
            return select_next_task(config=self._config)
