# SPDX-License-Identifier: MIT
"""Animation and output: keyframed parameters rebuild on frame change, Bake Animation keeps a mesh per frame and
swaps it in, Clear Bake puts the live mesh back; the Volume output adds a Mesh to Volume modifier."""

import bpy
import numpy as np
import pytest

from iteron.bridge import animation, volume
from iteron.bridge.props import group
from iteron.jobs import scheduler as scheduler_module
from iteron.jobs.scheduler import SCHEDULER


@pytest.fixture
def animated(fractal):
    obj = fractal("mandelbulb", resolution=32)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 3
    params = group(obj.iteron)
    for frame, power in ((1, 3.0), (3, 9.0)):
        params.power = power
        params.keyframe_insert("power", frame=frame)
    obj.iteron.final_resolution = 32
    obj.iteron.simplify = 0.0
    scene.frame_set(1)
    SCHEDULER.run_now(obj)
    return obj


def _centroid_spread(mesh) -> float:
    co = np.zeros(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", co)
    return float(np.linalg.norm(co.reshape(-1, 3), axis=1).std())


def test_a_keyframed_parameter_asks_for_a_rebuild_on_frame_change(animated, monkeypatch):
    monkeypatch.setattr(scheduler_module, "QUEUE_IN_BACKGROUND", True)
    bpy.context.scene.frame_set(3)
    assert SCHEDULER.status(animated) is not None
    SCHEDULER.cancel()


def test_bake_keeps_a_mesh_per_frame_and_swaps_them_in(animated):
    live = animated.data
    assert bpy.ops.iteron.bake_animation() == {"FINISHED"}
    assert [item.frame for item in animated.iteron.baked] == [1, 2, 3]
    assert animated.iteron.live_mesh == live
    meshes = {item.frame: item.mesh for item in animated.iteron.baked}
    assert _centroid_spread(meshes[1]) != pytest.approx(_centroid_spread(meshes[3]))
    bpy.context.scene.frame_set(2)
    assert animated.data == meshes[2]
    bpy.context.scene.frame_set(7)                            # past the range: the last frame
    assert animated.data == meshes[3]
    group(animated.iteron).power = 4.0                        # baked: no live rebuild
    assert "Baked" in animated.iteron.message
    assert bpy.ops.iteron.clear_bake() == {"FINISHED"}
    assert animated.data == live and len(animated.iteron.baked) == 0
    assert not [m for m in bpy.data.meshes if "· frame" in m.name]      # the baked meshes are gone


def test_volume_output_adds_and_removes_the_modifier(fractal):
    obj = fractal("mandelbulb", resolution=32)
    obj.iteron.output = "VOLUME"
    modifier = obj.modifiers[volume.MODIFIER]
    assert modifier.node_group.name == volume.GROUP
    depsgraph = bpy.context.evaluated_depsgraph_get()
    kinds = {i.object.type for i in depsgraph.object_instances if i.object.original == obj}
    assert "VOLUME" in kinds
    obj.iteron.output = "MESH"
    assert volume.MODIFIER not in obj.modifiers


def test_baking_is_not_disturbed_by_the_handlers(animated):
    animation.begin(animated)
    try:
        assert animated.session_uid in animation.BAKING
        bpy.context.scene.frame_set(2)                        # no swap, no request while baking
        assert animated.data == animated.iteron.live_mesh
    finally:
        animation.end(animated, 1)
