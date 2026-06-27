"""3D Scene Builder — bind OPC UA nodes to objects in a live three.js scene.

A scene is a list of :class:`Object3DConfig` items. Each object is a 3D shape
whose appearance/behaviour is driven by an OPC UA node:

  • binding ``read``  — a Variable's value drives a visual property
    (color / height / rotation / vertical position / visibility),
  • binding ``call``  — clicking the object invokes a Method,
  • binding ``write`` — clicking the object writes a value to a Variable.

The whole scene round-trips to/from a plain JSON dict so it can be saved and
shared.
"""

from app.widgets.scene3d.panel import Scene3DPanel

__all__ = ["Scene3DPanel"]
