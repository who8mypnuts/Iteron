# SPDX-License-Identifier: MIT
"""What differs between the kinds of fractal object — a formula, a flame, a fragment: the entry that describes
their parameters, reading and writing those, the digest of what shapes them, the job that builds them, and writing
the result. The scheduler, presets, panels and the live preview use these and nothing else, so every kind shares
its debounce, cancelling, progress, presets and main-thread writes."""

from __future__ import annotations

import hashlib
import json


def _digest(key) -> str:
    return hashlib.sha1(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()[:16]


class FormulaKind:
    cpu_fallback = True             # a failed GPU build may be retried on the CPU

    @staticmethod
    def entry(obj):
        """The formula (a hybrid composed from its current parts)."""
        from ..core.formula import REGISTRY
        from .props import group, stored
        base = REGISTRY[obj.iteron.formula]
        if base.compose is None:
            return base
        own = group(obj.iteron)
        return base.compose({p.name: getattr(own, p.name) for p in stored(base)})

    @staticmethod
    def read(obj) -> dict:
        from .props import read_values
        return read_values(obj.iteron)

    @staticmethod
    def write(obj, values: dict) -> None:
        from .props import write_values
        write_values(obj.iteron, values)

    @classmethod
    def shape_hash(cls, obj) -> str:
        s, entry = obj.iteron, cls.entry(obj)
        return _digest([entry.id, entry.version, cls.read(obj), s.auto_fit, tuple(round(c, 9) for c in s.center),
                        s.size, s.surface_offset, s.refine_steps, s.shading == "FIELD"])

    @classmethod
    def start(cls, obj, final: bool, force_cpu: bool):
        """`(job, spec, sampler name)`."""
        from ..jobs.pipeline import BuildSpec, build
        from ..jobs.scheduler import PREVIEW_REFINE
        s, entry = obj.iteron, cls.entry(obj)
        spec = BuildSpec(entry.id, cls.read(obj), tuple(s.center), s.size, s.auto_fit,
                         s.final_resolution if final else s.preview_resolution, s.surface_offset, final,
                         s.refine_steps if final else min(s.refine_steps, PREVIEW_REFINE), s.shading == "FIELD",
                         s.simplify if final else 0.0)
        sampler = cls.sampler(force_cpu)
        return build(spec, sampler, entry), spec, sampler.name

    @staticmethod
    def sampler(force_cpu: bool):
        from ..jobs.cpu_sampler import CpuSampler
        from ..jobs.scheduler import make_sampler
        return CpuSampler() if force_cpu else make_sampler()

    @staticmethod
    def finish(obj, result) -> None:
        from . import colors, mesh_write
        mesh_write.write(obj, result)
        colors.bake(obj)
        if result.channel_range is not None:
            obj.iteron.channel_lo = tuple(result.channel_range[0])
            obj.iteron.channel_hi = tuple(result.channel_range[1])


class FragmentKind(FormulaKind):
    """A Fragmentarium distance estimator: a formula whose kernel is the fragment's GLSL (GPU only)."""
    cpu_fallback = False

    @staticmethod
    def entry(obj):
        from ..fragments.formula import FragmentError, build
        from ..prefs import include_folders
        f = obj.iteron.fragment
        if f.text is None:
            raise FragmentError("the fragment's source text was removed from the file")
        return build(f.text.as_string(), None, include_folders(), f.name, prefer_shims=True)

    @classmethod
    def read(cls, obj) -> dict:
        from . import fragment_props
        return fragment_props.read(obj.iteron.fragment, cls.entry(obj).params)

    @classmethod
    def write(cls, obj, values: dict) -> None:
        from . import fragment_props
        fragment_props.write(obj.iteron.fragment, cls.entry(obj).params, values)

    @classmethod
    def shape_hash(cls, obj) -> str:
        try:
            return super().shape_hash(obj)
        except ValueError as error:              # the source doesn't build: stale until it does
            return _digest(["broken", str(error)])

    @staticmethod
    def sampler(force_cpu: bool):
        from ..fragments.formula import FragmentError
        from ..jobs.scheduler import make_sampler
        sampler = None if force_cpu else make_sampler()
        if sampler is None or sampler.name != "GPU":
            raise FragmentError("fragments are GLSL and build on the GPU only (no GPU is available here)")
        return sampler

    @classmethod
    def start(cls, obj, final: bool, force_cpu: bool):
        from . import fragment_props
        fragment_props.sync(obj.iteron.fragment, cls.entry(obj).params)
        return super().start(obj, final, force_cpu)


class FlameKind:
    cpu_fallback = False

    @staticmethod
    def shape_hash(obj) -> str:
        f = obj.iteron.flame
        return _digest([f.source, f.seed, f.output, f.threshold, f.smoothing])

    @staticmethod
    def start(obj, final: bool, _force_cpu: bool):
        from ..jobs.flame_pipeline import FlameSpec, build
        from .flame_props import PREVIEW_POINTS
        s, f = obj.iteron, obj.iteron.flame
        spec = FlameSpec(f.flame_dict(), f.points if final else min(f.points, PREVIEW_POINTS), f.seed, f.output,
                         s.final_resolution if final else s.preview_resolution, f.threshold, f.smoothing, final)
        return build(spec), spec, "CPU"

    @staticmethod
    def finish(obj, result) -> None:
        from . import flame_write
        flame_write.write(obj, result)
        obj.iteron.flame.unsupported = ", ".join(result.unsupported)


KINDS = {"FORMULA": FormulaKind, "FLAME": FlameKind, "FRAGMENT": FragmentKind}


def kind_of(obj):
    return KINDS[obj.iteron.kind]
