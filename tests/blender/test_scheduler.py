# SPDX-License-Identifier: MIT
"""The timed path the UI uses, driven by hand: requests, debounce, superseding, GPU turns, stalls, Edit Mode."""

import time

import pytest

import bpy
from iteron.bridge.props import group
from iteron.bridge.state import is_stale
from iteron.jobs import scheduler as sched
from iteron.jobs.scheduler import SCHEDULER


@pytest.fixture
def queued(monkeypatch):
    monkeypatch.setattr(sched, "QUEUE_IN_BACKGROUND", True)
    monkeypatch.setattr(sched, "make_sampler", lambda: sched.CpuSampler())
    yield
    SCHEDULER.reset()


def drive(draw=False, timeout=60.0):
    """Tick (and, with `draw`, play the viewport's draw callback) until the scheduler is idle."""
    end = time.monotonic() + timeout
    while SCHEDULER.busy() and time.monotonic() < end:
        SCHEDULER.tick()
        if draw:
            SCHEDULER.draw_callback()
        time.sleep(0.005)
    assert not SCHEDULER.busy(), "the scheduler did not finish"


def test_request_waits_for_the_debounce_then_builds(fractal, queued):
    obj = fractal("mandelbulb", resolution=24)
    group(obj.iteron).power = 5.0
    assert is_stale(obj) and SCHEDULER.busy(obj)
    SCHEDULER.tick()
    assert SCHEDULER.current is None, "started before the debounce elapsed"
    drive()
    assert not is_stale(obj) and obj.iteron.built_device == "CPU"


def test_a_running_preview_finishes_and_the_newest_request_follows(fractal, queued):
    obj = fractal("mandelbulb", resolution=24)
    group(obj.iteron).power = 5.0
    time.sleep(0.15)
    SCHEDULER.tick()
    assert SCHEDULER.current is not None
    group(obj.iteron).power = 6.0                   # while the first build runs
    assert SCHEDULER.current is not None and obj.session_uid in SCHEDULER.pending
    drive()
    assert not is_stale(obj)                         # the final mesh has the newest value


def test_a_change_cancels_a_running_final_build(fractal, queued):
    obj = fractal("sierpinski_tetrahedron", resolution=24)
    obj.iteron.final_resolution = 48
    SCHEDULER.request(obj, final=True)
    SCHEDULER.tick()
    assert SCHEDULER.current.final
    group(obj.iteron).scale = 2.2
    assert SCHEDULER.current is None                 # the final build was cancelled …
    assert not SCHEDULER.pending[obj.session_uid].final   # … and a preview of the new shape queued
    drive()
    assert not is_stale(obj)


def test_gpu_steps_only_advance_in_the_draw_callback(fractal, queued, monkeypatch, gpu_context):
    gpu_sampler = gpu_context
    monkeypatch.setattr(sched, "make_sampler", lambda: gpu_sampler.GpuSampler())
    obj = fractal("mandelbulb", resolution=24)
    group(obj.iteron).power = 7.0
    time.sleep(0.15)
    for _ in range(20):
        SCHEDULER.tick()
        if SCHEDULER.current and SCHEDULER.current.step.needs_gpu:
            break
    assert SCHEDULER.current.step.needs_gpu
    fraction = SCHEDULER.current.step.fraction
    SCHEDULER.tick()
    assert SCHEDULER.current.step.fraction == fraction, "a tick advanced a GPU step"
    drive(draw=True)
    assert obj.iteron.built_device == "GPU" and not is_stale(obj)


def test_a_gpu_build_with_no_viewport_drawing_moves_to_the_cpu(fractal, queued, monkeypatch, gpu_context):
    gpu_sampler = gpu_context
    monkeypatch.setattr(sched, "make_sampler", lambda: gpu_sampler.GpuSampler())
    monkeypatch.setattr(sched, "GPU_STALL", 0.05)
    obj = fractal("menger_sponge", resolution=24)
    group(obj.iteron).scale = 2.8
    drive(draw=False)
    assert obj.iteron.built_device == "CPU" and "CPU" in obj.iteron.message and not is_stale(obj)


def test_edit_mode_is_left_alone(fractal, queued):
    obj = fractal("octahedral_kifs", resolution=24)
    faces = len(obj.data.polygons)
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        group(obj.iteron).scale = 2.3
        assert not SCHEDULER.busy(obj)               # no request while editing
        SCHEDULER.request(obj)
        time.sleep(0.15)
        drive()
        assert "Edit Mode" in obj.iteron.message
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    assert len(obj.data.polygons) == faces
