"""Serializable data model for the 3D scene builder."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import uuid

# Allowed enum-ish string values (kept as plain strings for easy JSON + JS use).
# "text" is a label-only billboard (no mesh) handled by the web view.
SHAPES = ("box", "cylinder", "sphere", "cone", "text")
BINDINGS = ("read", "call", "write")
# What a read value drives on the object.
DRIVES = ("color", "scaleY", "rotateY", "posX", "posY", "posZ", "visible")


@dataclass
class Object3DConfig:
    """One bindable 3D object in the scene."""
    shape: str = "box"
    title: str = "Object"
    # World position.
    x: float = 0.0
    y: float = 0.5
    z: float = 0.0
    size: float = 1.0
    # Non-uniform dimensions (multipliers on ``size``). Allow wide/thin slabs,
    # shelves, drawers, masts, etc. A uniform cube keeps sx=sy=sz=1.
    sx: float = 1.0
    sy: float = 1.0
    sz: float = 1.0
    # Static rotation in degrees about each axis (e.g. to lay a cylinder flat).
    rx: float = 0.0
    ry: float = 0.0
    rz: float = 0.0
    color: str = "#6366f1"
    node_id: str = ""
    parent_id: str = ""        # owning object for a method (call binding)
    binding: str = "read"      # read | call | write
    drive: str = "color"       # read mode: which property the value drives
    min_value: float = 0.0
    max_value: float = 100.0
    write_value: str = ""      # write binding: value sent on click
    data_type: str = ""
    method_args: list = field(default_factory=list)
    # Live-data anchor key (e.g. "1/2/3"). Data sources place/remove a tube at
    # this object's position when its key is reported occupied.
    anchor: str = ""
    # Live-data tag: colour sources recolour all objects sharing this tag.
    tag: str = ""
    # Optional floating text label shown as a billboard near the object.
    label: str = ""
    # Optional clickable action: {endpoint, object, method, args} — calling an
    # OPC UA method when the object is clicked (e.g. a drawer Open/Close button).
    action: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Object3DConfig":
        shape = data.get("shape", "box")
        if shape not in SHAPES:
            shape = "box"
        binding = data.get("binding", "read")
        if binding not in BINDINGS:
            binding = "read"
        drive = data.get("drive", "color")
        if drive not in DRIVES:
            drive = "color"
        return cls(
            shape=shape,
            title=data.get("title", "Object"),
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.5)),
            z=float(data.get("z", 0.0)),
            size=float(data.get("size", 1.0)),
            sx=float(data.get("sx", 1.0)),
            sy=float(data.get("sy", 1.0)),
            sz=float(data.get("sz", 1.0)),
            rx=float(data.get("rx", 0.0)),
            ry=float(data.get("ry", 0.0)),
            rz=float(data.get("rz", 0.0)),
            color=data.get("color", "#6366f1"),
            node_id=data.get("node_id", ""),
            parent_id=data.get("parent_id", ""),
            binding=binding,
            drive=drive,
            min_value=float(data.get("min_value", 0.0)),
            max_value=float(data.get("max_value", 100.0)),
            write_value=data.get("write_value", ""),
            data_type=data.get("data_type", ""),
            method_args=list(data.get("method_args", [])),
            anchor=data.get("anchor", ""),
            tag=data.get("tag", ""),
            label=data.get("label", ""),
            action=dict(data.get("action", {}) or {}),
            id=data.get("id", uuid.uuid4().hex),
        )


@dataclass
class Scene3DModel:
    """A named collection of 3D objects."""
    name: str = "My 3D Scene"
    objects: list = field(default_factory=list)  # list[Object3DConfig]
    data_sources: list = field(default_factory=list)  # generic live-data bindings
    grids: list = field(default_factory=list)  # dynamic rack grids (data-driven)
    settings: dict = field(default_factory=dict)  # scene-level options (poll rate…)

    def to_dict(self) -> dict:
        return {
            "type": "opcua-scene3d",
            "version": 1,
            "name": self.name,
            "objects": [o.to_dict() for o in self.objects],
            "dataSources": self.data_sources,
            "grids": self.grids,
            "settings": self.settings,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Scene3DModel":
        objects = [Object3DConfig.from_dict(o) for o in data.get("objects", [])]
        return cls(
            name=data.get("name", "My 3D Scene"),
            objects=objects,
            data_sources=data.get("dataSources", []),
            grids=data.get("grids", []),
            settings=dict(data.get("settings", {}) or {}),
        )
