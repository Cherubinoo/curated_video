"""move / shift / scale / rotate."""
from __future__ import annotations

import math

import numpy as np

from animation_engine.components.base import RenderContext


def _mobjects(context: RenderContext, action):
    return [context.mobjects[t] for t in action.target_ids() if t in context.mobjects]


def move(scene, context: RenderContext, action):
    target_pos = context.resolve_position(action.to)
    return [m.animate.move_to(target_pos) for m in _mobjects(context, action)]


def shift(scene, context: RenderContext, action):
    delta = np.array([action.dx, action.dy, 0.0])
    return [m.animate.shift(delta) for m in _mobjects(context, action)]


def scale(scene, context: RenderContext, action):
    return [m.animate.scale(action.factor) for m in _mobjects(context, action)]


def rotate(scene, context: RenderContext, action):
    radians = math.radians(action.angle_degrees)
    return [m.animate.rotate(radians) for m in _mobjects(context, action)]
