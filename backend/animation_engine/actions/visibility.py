"""create / show / hide / write / fade_in / fade_out."""
from __future__ import annotations

from manim import Create, FadeIn, FadeOut, Write

from animation_engine.components.base import RenderContext


def _mobjects(context: RenderContext, action):
    return [context.mobjects[t] for t in action.target_ids() if t in context.mobjects]


def create(scene, context: RenderContext, action):
    return [Create(m) for m in _mobjects(context, action)]


def show(scene, context: RenderContext, action):
    mobjects = _mobjects(context, action)
    if mobjects:
        scene.add(*mobjects)
    return []


def hide(scene, context: RenderContext, action):
    mobjects = _mobjects(context, action)
    if mobjects:
        scene.remove(*mobjects)
    return []


def write(scene, context: RenderContext, action):
    return [Write(m) for m in _mobjects(context, action)]


def fade_in(scene, context: RenderContext, action):
    return [FadeIn(m) for m in _mobjects(context, action)]


def fade_out(scene, context: RenderContext, action):
    return [FadeOut(m) for m in _mobjects(context, action)]
