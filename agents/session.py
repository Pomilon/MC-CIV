import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Literal

from agents import config

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    cmd_id: str = ""
    status: Literal["completed", "failed", "cancelled"] = "completed"
    end_signal: str = ""
    error: str = ""
    observation: dict | None = None
    raw: dict | None = None


class PendingAction:
    def __init__(self, cmd_id: str, action: str, params: dict):
        self.cmd_id = cmd_id
        self.action = action
        self.params = params
        self.issued_at = time.time()
        self._event = asyncio.Event()

    @property
    def done(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> "PendingAction":
        await self._event.wait()
        return self

    def resolve(self, result: ActionResult) -> None:
        self.result = result
        self._event.set()


@dataclass
class Interrupt:
    type: Literal["chat", "event"]
    data: dict
    received_at: float = field(default_factory=time.time)


class AgentSession:
    def __init__(self, idle_timeout: float = config.IDLE_TIMEOUT):
        self.current_action: PendingAction | None = None
        self.interrupt_queue: asyncio.Queue[Interrupt] = asyncio.Queue()
        self.idle_timeout = idle_timeout

    def has_pending_action(self) -> bool:
        return self.current_action is not None and not self.current_action.done

    def start_action(self, cmd_id: str, action: str, params: dict) -> PendingAction:
        self.current_action = PendingAction(cmd_id=cmd_id, action=action, params=params)
        logger.info(f"Session: started action {action}[{cmd_id}]")
        return self.current_action

    def resolve_action(self, result: ActionResult) -> None:
        if self.current_action and not self.current_action.done and self.current_action.cmd_id == result.cmd_id:
            self.current_action.resolve(result)
            logger.info(f"Session: resolved {self.current_action.action}[{self.current_action.cmd_id}] -> {result.status}")

    def fail_action(self, error: str) -> None:
        if self.current_action and not self.current_action.done:
            self.current_action.resolve(ActionResult(status="failed", error=error))

    def cancel_action(self) -> None:
        if self.current_action and not self.current_action.done:
            self.current_action.resolve(ActionResult(status="cancelled", error="Cancelled by brain"))

    def push_interrupt(self, typ: Literal["chat", "event"], data: dict) -> None:
        self.interrupt_queue.put_nowait(Interrupt(type=typ, data=data))

    def drain_interrupts(self, max_count: int | None = None) -> list[Interrupt]:
        interrupts: list[Interrupt] = []
        while not self.interrupt_queue.empty():
            if max_count is not None and len(interrupts) >= max_count:
                break
            try:
                interrupts.append(self.interrupt_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return interrupts

    def clear_action(self) -> None:
        self.current_action = None

    async def wait_for_action_or_interrupt(self, timeout: float | None = None) -> tuple[Literal["done", "interrupt", "timeout"], Interrupt | None]:
        target_timeout = timeout if timeout is not None else self.idle_timeout

        if self.current_action and not self.current_action.done:
            interrupt_task = asyncio.ensure_future(self.interrupt_queue.get())
            action_task = asyncio.ensure_future(self.current_action.wait())

            done, pending = await asyncio.wait(
                [action_task, interrupt_task],
                timeout=target_timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )

            for t in pending:
                t.cancel()

            if action_task.done():
                return "done", None
            if interrupt_task.done():
                return "interrupt", interrupt_task.result()
            return "timeout", None
        else:
            try:
                interrupt = await asyncio.wait_for(self.interrupt_queue.get(), timeout=target_timeout)
                return "interrupt", interrupt
            except asyncio.TimeoutError:
                return "timeout", None
