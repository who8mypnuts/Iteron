# SPDX-License-Identifier: MIT
"""What a build job yields, and the helpers for driving one.

A job is a generator. Besides progress it can say *come back later* (`Waiting`: a worker thread is busy) or
*call me from a GPU context* (`GpuTurn`: the next step draws with the `gpu` module, which is only safe while Blender
is drawing). The scheduler honours both; `run_to_end` simply drives a job to completion (scripts, tests).
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Generator

_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="iteron")


class Waiting:
    """A worker thread is busy: come back later rather than spin."""

    def __init__(self, fraction: float | None = None):
        self.fraction = fraction


class GpuTurn:
    """The next step draws on the GPU: advance the job from a draw callback."""

    def __init__(self, fraction: float = 0.0):
        self.fraction = fraction


class Cancelled(Exception):
    """A job step noticed it was cancelled."""


class Cancel:
    """A flag workers poll; set when the job is superseded or cancelled."""

    def __init__(self):
        self._event = threading.Event()

    def set(self) -> None:
        self._event.set()

    def __call__(self) -> bool:
        return self._event.is_set()


def in_thread(fn: Callable[..., Any], *args, progress: list[float] | None = None) -> Generator[Waiting, None, Any]:
    """Run `fn(*args)` on the worker thread, yielding `Waiting` (with the shared progress value) until it is done;
    returns its result or re-raises its exception."""
    future: Future = _POOL.submit(fn, *args)
    while not future.done():
        yield Waiting(progress[0] if progress else None)
    return future.result()


def run_to_end(job: Generator) -> Any:
    """Drive a job synchronously, sleeping (not spinning) while a worker thread runs."""
    try:
        while True:
            step = next(job)
            if isinstance(step, Waiting) or getattr(step, "waiting", False):
                time.sleep(0.002)
    except StopIteration as done:
        return done.value
