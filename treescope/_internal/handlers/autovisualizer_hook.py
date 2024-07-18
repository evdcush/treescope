# Copyright 2024 The Treescope Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Handler for user-specified autovisualizers."""

from __future__ import annotations

from typing import Any

from treescope import autovisualize
from treescope import lowering
from treescope import renderer
from treescope import rendering_parts
from treescope._internal import object_inspection

IPythonVisualization = autovisualize.IPythonVisualization
CustomTreescopeVisualization = autovisualize.CustomTreescopeVisualization
ChildAutovisualizer = autovisualize.ChildAutovisualizer


def use_autovisualizer_if_present(
    node: Any,
    path: str | None,
    node_renderer: renderer.TreescopeSubtreeRenderer,
) -> (
    rendering_parts.RenderableTreePart
    | rendering_parts.RenderableAndLineAnnotations
    | type(NotImplemented)
):
  """Treescope wrapper hook that runs the active autovisualizer."""
  autoviz = autovisualize.active_autovisualizer.get()
  result = autoviz(node, path)
  if result is None:
    # Continue as normal.
    return NotImplemented

  elif isinstance(result, IPythonVisualization | CustomTreescopeVisualization):
    # We should use this visualization instead.

    # Fallback: Render normally for round-trip mode, and if this wasn't a
    # replaced object.
    with autovisualize.active_autovisualizer.set_scoped(
        lambda value, path: None
    ):
      ordinary_result = node_renderer(node, path)

    if isinstance(result, IPythonVisualization):
      if isinstance(result.display_object, object_inspection.HasReprHtml):
        obj = result.display_object

        def _thunk(_):
          html_rendering = object_inspection.to_html(obj)
          if html_rendering:
            return rendering_parts.embedded_iframe(
                embedded_html=html_rendering,
                fallback_in_text_mode=rendering_parts.abbreviation_color(
                    rendering_parts.text("<rich HTML visualization>")
                ),
            )
          else:
            return rendering_parts.error_color(
                rendering_parts.text(
                    "<Autovisualizer returned a Visualization with an invalid"
                    f" display object {result.display_object}>"
                )
            )

        ipy_rendering = lowering.maybe_defer_rendering(
            _thunk,
            lambda: rendering_parts.text(
                "<rich HTML visualization loading...>"
            ),
        )
      else:
        # Bad display object
        ipy_rendering = rendering_parts.build_one_line_tree_node(
            line=rendering_parts.error_color(
                rendering_parts.text(
                    "<Autovisualizer returned a Visualization with an invalid"
                    f" display object {result.display_object}>"
                )
            ),
            path=path,
        )
      if result.replace:
        replace = True
        rendering_and_annotations = (
            rendering_parts.build_custom_foldable_tree_node(
                label=rendering_parts.abbreviation_color(
                    rendering_parts.text(
                        f"<Visualization of {type(node).__name__}"
                    )
                ),
                contents=rendering_parts.siblings(
                    rendering_parts.fold_condition(
                        expanded=rendering_parts.siblings(
                            rendering_parts.abbreviation_color(
                                rendering_parts.text(":")
                            ),
                            rendering_parts.indented_children([ipy_rendering]),
                        )
                    ),
                    rendering_parts.abbreviation_color(
                        rendering_parts.text(">")
                    ),
                ),
                path=path,
                expand_state=rendering_parts.ExpandState.EXPANDED,
            )
        )
      else:
        replace = False
        rendering_and_annotations = rendering_parts.RenderableAndLineAnnotations(
            renderable=rendering_parts.floating_annotation_with_separate_focus(
                rendering_parts.in_outlined_box(ipy_rendering)
            ),
            annotations=rendering_parts.empty_part(),
        )
    else:
      assert isinstance(result, CustomTreescopeVisualization)
      replace = True
      rendering_and_annotations = result.rendering

    if replace:
      in_roundtrip_with_annotations = rendering_parts.siblings_with_annotations(
          ordinary_result,
          extra_annotations=[
              rendering_parts.comment_color(
                  rendering_parts.text(
                      "  # Visualization hidden in roundtrip mode"
                  )
              )
          ],
      )
      return rendering_parts.RenderableAndLineAnnotations(
          renderable=rendering_parts.roundtrip_condition(
              roundtrip=in_roundtrip_with_annotations.renderable,
              not_roundtrip=rendering_and_annotations.renderable,
          ),
          annotations=rendering_parts.roundtrip_condition(
              roundtrip=in_roundtrip_with_annotations.annotations,
              not_roundtrip=rendering_and_annotations.annotations,
          ),
      )
    else:
      return rendering_parts.siblings_with_annotations(
          ordinary_result, rendering_and_annotations
      )

  elif isinstance(result, ChildAutovisualizer):
    # Use a different autovisualizer while rendering this object.
    with autovisualize.active_autovisualizer.set_scoped(result.autovisualizer):
      return node_renderer(node, path)

  else:
    return rendering_parts.build_one_line_tree_node(
        line=rendering_parts.error_color(
            rendering_parts.text(
                f"<Autovizualizer returned an invalid value {result}; expected"
                " IPythonVisualization, CustomTreescopeVisualization,"
                " ChildAutovisualizer, or None>"
            )
        ),
        path=path,
    )
