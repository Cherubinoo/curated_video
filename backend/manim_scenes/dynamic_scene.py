"""Entrypoint module for the Manim CLI: `manim render manim_scenes/dynamic_scene.py SpecificationScene`.

The actual Scene implementation lives in
`animation_engine.renderer.scene_builder` (it's part of the animation
engine, not Manim-CLI plumbing). Manim's scene discovery
(`manim.utils.module_ops.get_scene_classes_from_module`) only picks up
classes whose `__module__` belongs to the file it loaded - a plain
re-export (`from ... import SpecificationScene`) keeps the original
`animation_engine.renderer.scene_builder` module name and is invisible to
that filter, so this thin subclass exists purely to be "born" in this
module while inheriting 100% of the real behavior.
"""
from animation_engine.renderer.scene_builder import SpecificationScene as _SpecificationScene


class SpecificationScene(_SpecificationScene):
    pass
