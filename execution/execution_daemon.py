"""Thin simulation execution coordinator."""

from __future__ import annotations

from execution.models import ExecutionResult, SimulationOrderRequest
from execution.simulation_broker import SimulationBroker


class ExecutionDaemon:
    """Coordinate one paper request at a time; no live loop exists here."""

    def __init__(self, broker: SimulationBroker) -> None:
        self.broker = broker

    def process(self, request: SimulationOrderRequest) -> ExecutionResult:
        return self.broker.submit(request)

