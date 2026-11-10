# SPDX-License-Identifier: MIT
"""The command line: list the formulas, and mesh a formula, a fragment or a flame to a file.

    python -m iteron.cli formulas
    python -m iteron.cli mesh mandelbulb -s power=9 -r 256 -o bulb.ply
    python -m iteron.cli fragment "Juliabulb.frag" --preset Default -r 192 -o julia.obj
    python -m iteron.cli flame sierpinski_pyramid -n 2000000 -o pyramid.ply          (points; --solid for a mesh)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

CHANNELS = {"trap": 0, "iterations": 1, "radius": 2}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.run(args)
    except (ValueError, KeyError, OSError, RuntimeError) as error:
        print(f"iteron: {error}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m iteron.cli", description="Mesh Iteron fractals without Blender.")
    commands = parser.add_subparsers(required=True, metavar="command")
    listing = commands.add_parser("formulas", help="list the formulas, their parameters and presets")
    listing.set_defaults(run=list_formulas)

    def meshing(name: str, help_text: str, run, target: str):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument(target)
        sub.add_argument("-o", "--output", required=True, type=Path, help="the file to write (.ply or .obj)")
        sub.add_argument("-r", "--resolution", type=int, default=192, help="voxels along the longest side")
        sub.add_argument("-q", "--quiet", action="store_true", help="no progress on stderr")
        sub.set_defaults(run=run)
        return sub

    for name, run, target in (("mesh", mesh_formula, "formula"), ("fragment", mesh_fragment, "file")):
        sub = meshing(name, f"mesh a {'formula' if name == 'mesh' else '.frag / .fafrag file'}", run, target)
        sub.add_argument("-s", "--set", action="append", default=[], metavar="NAME=VALUE",
                         help="a parameter value (vectors as 1,2,3; booleans true/false)")
        sub.add_argument("--preset", help="start from a preset")
        sub.add_argument("--refine", type=int, default=2, help="Newton steps onto the true surface")
        sub.add_argument("--simplify", type=float, default=0.1, help="merge flat areas within this many voxels")
        sub.add_argument("--offset", type=float, default=None, help="surface offset, voxels")
        sub.add_argument("--color", choices=tuple(CHANNELS), default="trap", help="what the vertex colours show")
        if name == "mesh":
            sub.add_argument("--gpu", action="store_true", help="sample with moderngl (OpenGL 3.3) instead of numpy")
        else:
            sub.add_argument("-I", "--include", action="append", default=[], help="a folder searched for includes")
    flame = meshing("flame", "a flame as points (or --solid) from the library or a .fa / .fa3d / .flame file", mesh_flame,
                    "flame")
    flame.add_argument("-n", "--points", type=int, default=1_000_000)
    flame.add_argument("--index", type=int, default=0, help="which flame of a .fa or .flame file (from 0)")
    flame.add_argument("--seed", type=int, default=1)
    flame.add_argument("--solid", action="store_true", help="a density mesh instead of points")
    flame.add_argument("--threshold", type=float, default=0.15)
    flame.add_argument("--smoothing", type=float, default=1.0)
    return parser


def list_formulas(_args) -> int:
    from .. import formulas  # noqa: F401  (registers the formulas)
    from ..core.formula import REGISTRY
    for entry in REGISTRY.values():
        print(f"{entry.id:24s} {entry.name} — {entry.description}")
        for p in entry.params:
            print(f"    {p.name:18s} {p.kind:6s} default {p.default!r}")
        if entry.presets:
            print(f"    presets: {', '.join(entry.presets)}")
    return 0


def parse_sets(entry, pairs: list[str], preset: str | None) -> dict:
    values = dict(entry.presets[preset]) if preset else {}
    if entry.compose is not None:                      # a hybrid: its parts decide which parameters exist
        from ..core.formula import concrete
        chosen = dict(pair.split("=", 1) for pair in pairs if pair.split("=", 1)[0] in entry.stored)
        entry = concrete(entry, {**values, **chosen})
    params = {p.name: p for p in entry.params}
    for pair in pairs:
        name, sep, text = pair.partition("=")
        if not sep or name not in params:
            raise KeyError(f"unknown parameter {name!r}; {entry.id} has: {', '.join(params)}")
        param = params[name]
        if param.kind == "bool":
            values[name] = text.strip().lower() in ("1", "true", "yes", "on")
        elif param.lanes > 1:
            values[name] = tuple(float(v) for v in text.split(","))
        else:
            values[name] = text.strip() if param.kind == "enum" else float(text)
    return entry.values(values)


def drive(job, quiet: bool):
    """Run a build job, printing its stages."""
    from ..jobs.steps import Waiting
    last, shown = "", 0.0
    try:
        while True:
            step = next(job)
            message = getattr(step, "message", "")
            if not quiet and (message != last or time.monotonic() - shown > 2.0):
                print(f"  {getattr(step, 'fraction', 0.0) * 100:5.1f} %  {message}", file=sys.stderr)
                last, shown = message, time.monotonic()
            if isinstance(step, Waiting) or getattr(step, "waiting", False):
                time.sleep(0.002)
    except StopIteration as done:
        return done.value


def _write_mesh(args, result) -> int:
    from ..core.palette import sweep
    from .writers import write
    colours = sweep(result.channels[:, CHANNELS[args.color]])
    path = write(args.output, result.vertices, [result.quads, result.tris if result.tris is not None else []],
                 colours, result.normals)
    print(f"{path}: {len(result.vertices):,} vertices, {result.faces:,} faces, {result.seconds:.1f} s on the "
          f"{result.sampler}")
    return 0


def _spec(args, entry, values, center=(0.0, 0.0, 0.0)):
    from ..jobs.pipeline import BuildSpec
    offset = entry.surface_offset if args.offset is None else args.offset
    return BuildSpec(entry.id, values, tuple(center), 0.0, True, args.resolution, offset, True, args.refine, True,
                     args.simplify)


def _gl_sampler():
    from .gl_sampler import GlSampler, context
    ctx = context()
    if ctx is None:
        raise RuntimeError("no OpenGL 3.3 context: install moderngl (pip install moderngl) and a GPU driver or Mesa")
    return GlSampler(ctx)


def mesh_formula(args) -> int:
    from .. import formulas  # noqa: F401  (registers the formulas)
    from ..core.formula import REGISTRY
    from ..jobs.cpu_sampler import CpuSampler
    from ..jobs.pipeline import build
    if args.formula not in REGISTRY:
        raise KeyError(f"unknown formula {args.formula!r} (see `formulas`)")
    entry = REGISTRY[args.formula]
    values = parse_sets(entry, args.set, args.preset)
    sampler = _gl_sampler() if args.gpu else CpuSampler()
    return _write_mesh(args, drive(build(_spec(args, entry, values), sampler, entry), args.quiet))


def mesh_fragment(args) -> int:
    from ..fragments.formula import build as build_fragment, embeddable
    from ..jobs.pipeline import build
    path = Path(args.file)
    entry = build_fragment(embeddable(path, tuple(args.include)), path.stem, prefer_shims=True)
    values = parse_sets(entry, args.set, args.preset or next(iter(entry.presets), None))
    center = entry.camera.target if entry.camera else (0.0, 0.0, 0.0)
    return _write_mesh(args, drive(build(_spec(args, entry, values, center), _gl_sampler(), entry), args.quiet))


def mesh_flame(args) -> int:
    from ..flames import formats
    from ..flames.library import bundled
    from ..jobs.flame_pipeline import MESH, POINTS, FlameSpec, build
    from .writers import write
    source = Path(args.flame)
    if source.suffix.lower() in (".fa", ".flame"):
        from ..flames.flame_xml import read_flame
        flames = formats.read_fa(source) if source.suffix.lower() == ".fa" else read_flame(source)
        flame = flames[args.index].to_dict()
    elif source.suffix.lower() == ".fa3d":
        flame = formats.read_fa3d(source).flame.to_dict()
    elif args.flame in bundled():
        flame = bundled()[args.flame]
    else:
        raise KeyError(f"no flame {args.flame!r}: give a .fa / .fa3d / .flame file or one of {', '.join(bundled())}")
    spec = FlameSpec(flame, args.points, args.seed, MESH if args.solid else POINTS, args.resolution, args.threshold,
                     args.smoothing, True)
    result = drive(build(spec), args.quiet)
    write(args.output, result.vertices, [result.quads], result.colours)
    print(f"{args.output}: {len(result.vertices):,} {'vertices' if args.solid else 'points'}, {result.faces:,} faces"
          + (f" (not available, skipped: {', '.join(result.unsupported)})" if result.unsupported else ""))
    return 0
