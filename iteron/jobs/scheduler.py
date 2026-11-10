# SPDX-License-Identifier: MIT
"""Runs builds between UI events: a queue of requests, one job at a time.

Rules: a request waits out a short debounce (so a slider drag starts one build, not fifty); the active object goes
first; a newer request for an object replaces its pending one; a running *preview* is allowed to finish (so
dragging keeps updating) while a running *final* build is cancelled by any change (its result would be stale).

A Blender timer advances the job for a few milliseconds per tick. Steps that draw with the `gpu` module
(`Step.needs_gpu`) are advanced from a 3D viewport draw callback instead, the one place Blender guarantees a GPU
context on every backend; if no viewport draws for a while, the build moves to the CPU. Results are written to the
mesh from the timer, never while drawing. In background mode nothing ticks: `run_now` builds synchronously.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field

import bpy

from .cpu_sampler import CpuSampler
from .pipeline import Step
from .steps import Cancelled, run_to_end

TICK = 0.02            # seconds between ticks while there is work
BUDGET = 0.03          # seconds of work per tick or per draw callback
GPU_STALL = 1.5        # seconds without a viewport draw before a GPU build moves to the CPU
PREVIEW_REFINE = 1     # previews refine at most this many steps (finals take the setting)
QUEUE_IN_BACKGROUND = False      # tests set this to drive the timed path by calling `tick()` themselves


@dataclass
class Request:
    uid: int
    name: str
    final: bool
    due: float


@dataclass
class Running:
    uid: int
    name: str
    final: bool
    job: object
    spec: object                   # the kind's build spec (its `resolution` is recorded)
    shape: str
    sampler: str
    step: Step = field(default_factory=lambda: Step(0.0, "Starting"))
    fallback: bool = False
    gpu_wait: float = 0.0          # when the job started waiting for a draw callback


def find_object(uid: int, name: str):
    """The object by name if its session uid still matches (renames are followed by a scan), else None."""
    obj = bpy.data.objects.get(name)
    if obj is not None and obj.session_uid == uid:
        return obj
    return next((o for o in bpy.data.objects if o.session_uid == uid), None)


class Scheduler:
    def __init__(self):
        self.pending: dict[int, Request] = {}
        self.current: Running | None = None

    # --- requests ----------------------------------------------------------------------------------------------
    def request(self, obj, final: bool = False) -> None:
        """Queue a build. A no-op in background mode, where nothing ticks: scripts build with `run_now`."""
        from ..prefs import preferences
        if bpy.app.background and not QUEUE_IN_BACKGROUND:
            return
        uid = obj.session_uid
        if self.current and self.current.uid == uid and (final or self.current.final):
            self._close_current()
        delay = 0.0 if final else preferences().debounce / 1000.0
        keep_final = uid in self.pending and self.pending[uid].final
        self.pending[uid] = Request(uid, obj.name, final or keep_final, time.monotonic() + delay)
        if not bpy.app.background and not bpy.app.timers.is_registered(self.tick):
            bpy.app.timers.register(self.tick, first_interval=delay)

    def cancel(self, obj=None) -> None:
        """Drop pending and running work (for `obj`, or everything)."""
        uid = obj.session_uid if obj is not None else None
        for key in [k for k in self.pending if uid is None or k == uid]:
            del self.pending[key]
        if self.current and (uid is None or self.current.uid == uid):
            self._close_current()

    def reset(self) -> None:
        self.cancel()

    def status(self, obj) -> Running | Request | None:
        if self.current and self.current.uid == obj.session_uid:
            return self.current
        return self.pending.get(obj.session_uid)

    def busy(self, obj=None) -> bool:
        if obj is not None:
            return self.status(obj) is not None
        return self.current is not None or bool(self.pending)

    # --- synchronous ------------------------------------------------------------------------------------------
    def run_now(self, obj, final: bool = False) -> None:
        """Build `obj` right away, blocking (background mode and scripts)."""
        self.pending.pop(obj.session_uid, None)
        running = self._try_start(obj, final)
        if running is None:
            return
        try:
            result = run_to_end(running.job)
        except Exception as error:      # noqa: BLE001 - reported on the object, like the timed path
            if not self._fall_back(running, error):
                self._report(obj, error)
                return
            result = run_to_end(running.job)
        self._finish(obj, running, result)

    # --- the timer ---------------------------------------------------------------------------------------------
    def tick(self) -> float | None:
        try:
            if self.current is None:
                self._start_next()
            running = self.current
            if running is not None and running.step.needs_gpu:
                self._await_draw(running)
            elif running is not None:
                self._advance(gpu_context=False)
        except Exception:               # noqa: BLE001 - a timer must never raise; keep the add-on usable
            traceback.print_exc()
            self.current = None
        _redraw("UI")
        return TICK if (self.current or self.pending) else None

    def draw_callback(self) -> None:
        """Advance GPU steps (registered as a SpaceView3D draw handler)."""
        running = self.current
        if running is not None and running.step.needs_gpu:
            try:
                self._advance(gpu_context=True)
            except Exception:           # noqa: BLE001 - never break viewport drawing
                traceback.print_exc()
                self.current = None

    def _await_draw(self, running: Running) -> None:
        now = time.monotonic()
        running.gpu_wait = running.gpu_wait or now
        if now - running.gpu_wait > GPU_STALL:
            from ..bridge.kinds import kind_of
            obj = find_object(running.uid, running.name)
            if obj is not None and not kind_of(obj).cpu_fallback:
                obj.iteron.message = "Waiting for a 3D viewport to draw (this builds on the GPU only)"
                running.gpu_wait = now
            elif obj is not None:
                self.current = self._try_start(obj, running.final, force_cpu=True)
                obj.iteron.message = "No 3D viewport was drawing; built on the CPU"
            else:
                self.current = None
                return
        _redraw("WINDOW")

    def _advance(self, gpu_context: bool) -> None:
        deadline = time.monotonic() + BUDGET
        while self.current and time.monotonic() < deadline:
            running = self.current
            if running.step.needs_gpu != gpu_context:
                return                      # the next step belongs to the other driver
            try:
                step = next(running.job)
            except StopIteration as done:
                if gpu_context:             # never write data while drawing: let the timer finish it
                    running.step = Step(1.0, "Writing", needs_gpu=False)
                    running.job = _finished(done.value)
                    return
                self.current = None
                obj = find_object(running.uid, running.name)
                if obj is not None:
                    self._finish(obj, running, done.value)
                return
            except Cancelled:
                self.current = None
                return
            except Exception as error:      # noqa: BLE001
                obj = find_object(running.uid, running.name)
                if not self._fall_back(running, error):
                    self.current = None
                    if obj is not None:
                        self._report(obj, error)
                return
            running.step, running.gpu_wait = step, 0.0
            if step.waiting:
                return

    def _start_next(self) -> None:
        now = time.monotonic()
        due = [r for r in self.pending.values() if r.due <= now]
        if not due:
            return
        active = getattr(bpy.context, "active_object", None)
        request = next((r for r in due if active is not None and r.uid == active.session_uid), due[0])
        del self.pending[request.uid]
        obj = find_object(request.uid, request.name)
        if obj is None or not obj.iteron.is_fractal:
            return
        if obj.mode == "EDIT":
            obj.iteron.message = "Not rebuilt while in Edit Mode"
            return
        self.current = self._try_start(obj, request.final)

    # --- jobs ----------------------------------------------------------------------------------------------------
    def _start(self, obj, final: bool, force_cpu: bool = False) -> Running:
        from ..bridge.kinds import kind_of
        kind = kind_of(obj)
        job, spec, sampler = kind.start(obj, final, force_cpu)
        return Running(obj.session_uid, obj.name, final, job, spec, kind.shape_hash(obj), sampler,
                       fallback=force_cpu)

    def _try_start(self, obj, final: bool, force_cpu: bool = False) -> Running | None:
        """`_start`, with a failure (a fragment that doesn't parse, no GPU for one) reported on the object."""
        try:
            return self._start(obj, final, force_cpu)
        except Exception as error:      # noqa: BLE001
            self._report(obj, error)
            return None

    def _fall_back(self, running: Running, error: Exception) -> bool:
        """The GPU path failed: retry the same build on the CPU (once, for kinds that can). Mutates `running`."""
        from ..bridge.kinds import kind_of
        if running.sampler != "GPU" or running.fallback:
            return False
        obj = find_object(running.uid, running.name)
        if obj is None or not kind_of(obj).cpu_fallback:
            return False
        traceback.print_exception(error)
        replacement = self._try_start(obj, running.final, force_cpu=True)
        if replacement is None:
            return False
        running.job, running.sampler, running.fallback, running.spec = (replacement.job, replacement.sampler, True,
                                                                        replacement.spec)
        running.step = Step(0.0, "Retrying on the CPU")
        obj.iteron.message = f"GPU sampling failed ({error}); used the CPU"
        return True

    def _finish(self, obj, running: Running, result) -> None:
        from ..bridge.display import sync
        from ..bridge.kinds import kind_of
        if obj.mode == "EDIT":
            obj.iteron.message = "Not rebuilt while in Edit Mode"
            return
        kind_of(obj).finish(obj, result)
        s = obj.iteron
        s.built_hash, s.built_resolution, s.built_final = running.shape, running.spec.resolution, running.final
        s.built_faces, s.built_seconds, s.built_device = result.faces, result.seconds, result.sampler
        if not running.fallback:
            s.message = ""
        sync(obj)

    def _report(self, obj, error: Exception) -> None:
        if not getattr(error, "user_facing", False):     # a bug: keep the traceback; a known limit only says why
            traceback.print_exception(error)
        obj.iteron.message = f"Build failed: {error}"

    def _close_current(self) -> None:
        if self.current is not None:
            self.current.job.close()
            self.current = None


def _finished(value):
    """A job that immediately returns `value` (hands a result from a draw callback to the timer)."""
    return value
    yield  # noqa: unreachable - makes this a generator


def make_sampler():
    """The GPU sampler when the preferences allow it and Blender has a GPU backend here; else the CPU one."""
    from ..prefs import preferences
    if preferences().device != "CPU":
        from ..gpu_eval import sampler as gpu_sampler
        if gpu_sampler.available():
            return gpu_sampler.GpuSampler()
    return CpuSampler()


def _redraw(region_type: str) -> None:
    """Tag the 3D viewports' `region_type` regions: "UI" for the sidebar's progress, "WINDOW" for a GPU turn."""
    for window in getattr(bpy.context.window_manager, "windows", ()):
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                for region in area.regions:
                    if region.type == region_type:
                        region.tag_redraw()


SCHEDULER = Scheduler()
_DRAW_HANDLE = None


def register() -> None:
    global _DRAW_HANDLE
    _DRAW_HANDLE = bpy.types.SpaceView3D.draw_handler_add(SCHEDULER.draw_callback, (), "WINDOW", "POST_PIXEL")


def unregister() -> None:
    global _DRAW_HANDLE
    SCHEDULER.reset()
    if bpy.app.timers.is_registered(SCHEDULER.tick):
        bpy.app.timers.unregister(SCHEDULER.tick)
    if _DRAW_HANDLE is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_DRAW_HANDLE, "WINDOW")
        _DRAW_HANDLE = None
