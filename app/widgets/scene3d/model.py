"""Serializable data model for the 3D scene builder."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import uuid

# Allowed enum-ish string values (kept as plain strings for easy JSON + JS use).
SHAPES = ("box", "cylinder", "sphere", "cone")
BINDINGS = ("read", "call", "write")
# What a read value drives on the object.
DRIVES = ("color", "scaleY", "rotateY", "posY", "visible")


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
    color: str = "#6366f1"
    # OPC UA binding.
    node_id: str = ""
    parent_id: str = ""        # owning object for a method (call binding)
    binding: str = "read"      # read | call | write
    drive: str = "color"       # read mode: which property the value drives
    min_value: float = 0.0
    max_value: float = 100.0
    write_value: str = ""      # write binding: value sent on click
    data_type: str = ""
    method_args: list = field(default_factory=list)
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
            id=data.get("id", uuid.uuid4().hex),
        )


@dataclass
class Scene3DModel:
    """A named collection of 3D objects."""
    name: str = "My 3D Scene"
    objects: list = field(default_factory=list)  # list[Object3DConfig]

    def to_dict(self) -> dict:
        return {
            "type": "opcua-scene3d",
            "version": 1,
            "name": self.name,
            "objects": [o.to_dict() for o in self.objects],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Scene3DModel":
        objects = [Object3DConfig.from_dict(o) for o in data.get("objects", [])]
        return cls(name=data.get("name", "My 3D Scene"), objects=objects)
