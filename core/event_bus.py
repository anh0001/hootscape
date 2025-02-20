import asyncio
from typing import Callable, Awaitable, Dict, List, Any

class EventBus:
    def __init__(self):
        # Dictionary mapping event names to lists of subscriber callbacks.
        self._subscribers: Dict[str, List[Callable[..., Awaitable[Any]]]] = {}

    def subscribe(self, event: str, callback: Callable[..., Awaitable[Any]]) -> None:
        if event not in self._subscribers:
            self._subscribers[event] = []
        self._subscribers[event].append(callback)

    async def publish(self, event: str, *args, **kwargs) -> None:
        if event in self._subscribers:
            # Launch all subscriber callbacks concurrently.
            await asyncio.gather(*(subscriber(*args, **kwargs) for subscriber in self._subscribers[event]))