"""Shared pieces for the tests: the project root, one cached build, and a small made-up panel."""
from __future__ import annotations

import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cwc import __main__ as cli  # noqa: E402

_CACHE = {}


def built():
    """(findings, files) from one rebuild, shared by every test that only reads it."""
    if "build" not in _CACHE:
        _CACHE["build"] = cli.build(ROOT)
    return _CACHE["build"]


def wave(t: int, period: float, phase: float) -> float:
    return math.sin(2.0 * math.pi * (t + phase) / period)


def panel(n_pre: int, n_post: int, shift: float, weights=(0.6, 0.4, 0.0), noise: float = 0.03):
    """A treated series that is an exact mix of three donors plus small fixed wiggles, shifted by `shift` after the event."""
    total = n_pre + n_post
    donors = [
        [10.0 + 0.30 * wave(t, 7.0, 0.0) + 0.02 * t for t in range(total)],
        [9.0 + 0.25 * wave(t, 5.0, 1.0) - 0.01 * t for t in range(total)],
        [8.0 + 0.20 * wave(t, 11.0, 2.0) for t in range(total)],
    ]
    x = [[donors[j][t] for j in range(3)] for t in range(total)]
    y = []
    for t in range(total):
        value = 0.7 + sum(w * donors[j][t] for j, w in enumerate(weights))
        value += noise * wave(t, 3.3, 0.4) + 0.5 * noise * wave(t, 6.1, 2.2)
        y.append(value + (shift if t >= n_pre else 0.0))
    return y, x
