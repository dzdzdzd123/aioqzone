"""
Define hooks that can trigger user actions.
"""

import asyncio
from collections import defaultdict
from typing import Awaitable, Callable, Generic, TypeVar


class Event:
    """Base class for event system."""

    pass


Evt = TypeVar("Evt", bound=Event)
T = TypeVar("T")


class NullEvent(Event):
    """For debugging"""

    __slots__ = ()

    def __getattribute__(self, __name: str):
        assert False, "call `o.register_hook` before accessing o.hook"


class Emittable(Generic[Evt]):
    """An object has some event to trigger."""

    hook: Evt = NullEvent()  # type: ignore
    _tasks: dict[str, set[asyncio.Task]]
    _loop: asyncio.AbstractEventLoop

    def __init__(self) -> None:
        self._tasks = defaultdict(set)
        self._loop = asyncio.get_event_loop()

    def register_hook(self, hook: Evt):
        assert not isinstance(hook, NullEvent)
        self.hook = hook

    def add_hook_ref(self, hook_cls: str, coro: Awaitable[T]) -> asyncio.Task[T]:
        task = self._loop.create_task(coro)  # type: ignore
        self._tasks[hook_cls].add(task)
        task.add_done_callback(lambda t: self._tasks[hook_cls].remove(t))
        return task  # type: ignore

    async def wait(
        self,
        *hook_cls: str,
        timeout: float | None = None,
    ) -> tuple[set[asyncio.Task], set[asyncio.Task]]:
        """Wait for all task in the specific task set(s).

        :param timeout: timeout, defaults to None
        :type timeout: float, optional
        :return: done, pending

        .. note::
            If `timeout` is None, this method will loop until all tasks in the set(s) are done.
            That means if other tasks are added during awaiting, the added task will be waited as well.

        .. seealso:: :meth:`asyncio.wait`
        """
        s = set()
        for i in hook_cls:
            s |= self._tasks[i]
        if not s:
            return set(), set()
        r = await asyncio.wait(s, timeout=timeout)
        if timeout is None and any(self._tasks[i] for i in hook_cls):
            # await potential new tasks in these sets, only if no timeout.
            r2 = await Emittable.wait(self, *hook_cls)
            return r[0] | r2[0], set()
        return r

    def clear(self, *hook_cls: str, cancel: bool = True):
        """Clear the given task sets

        :param hook_cls: task class names
        :param cancel: Cancel the task if a set is not empty, defaults to True. Else will just clear the ref.
        """
        for i in hook_cls:
            s = self._tasks[i]
            if s and not cancel:
                s.clear()
                continue
            while s:
                t = s.pop()
                t.cancel()


class LoginEvent(Event):
    """Defines usual events happens during login."""

    async def LoginFailed(self, msg: str | None = None):
        """Will be emitted on login failed.

        .. note::
            This event will be triggered on every failure of login attempt.
            Means that logic in this event may be executed multiple times.

        :param msg: Err msg, defaults to None.
        """
        pass

    async def LoginSuccess(self):
        """Will be emitted after login success. Low prior, scheduled by loop instead of awaiting."""
        pass


class QREvent(LoginEvent):
    """Defines usual events happens during QR login."""

    cancel: Callable[[], Awaitable[None]] | None
    resend: Callable[[], Awaitable[None]] | None

    async def QrFetched(self, png: bytes, renew: bool = False):
        """Will be called on new QR code bytes are fetched. Means this will be triggered on:
        1. QR login start
        2. QR expired
        3. QR is refreshed

        :param png: QR bytes (png format)
        :param renew: this QR is a refreshed QR, defaults to False

        .. warning::
            Develpers had better not rely on the parameter :param renew:.
            Maintain the state by yourself is not difficult.
        """
        pass

    async def QrFailed(self, msg: str | None = None):
        """QR login failed.

        .. note: This event should always be called before :meth:`.LoginEvent.LoginFailed`.

        :param msg: Error msg, defaults to None.
        """
        pass

    async def QrSucceess(self):
        """QR login success."""
        pass
