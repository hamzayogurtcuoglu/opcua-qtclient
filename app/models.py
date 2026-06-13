"""Data models for the OPC UA Client application."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ConnectionStatus(Enum):
    """Connection status for OPC UA servers."""
    DISCONNECTED = "Disconnected"
    CONNECTING = "Connecting..."
    CONNECTED = "Connected"
    ERROR = "Error"


class NodeType(Enum):
    """OPC UA node class types."""
    OBJECT = "Object"
    VARIABLE = "Variable"
    METHOD = "Method"
    VIEW = "View"
    OBJECT_TYPE = "ObjectType"
    VARIABLE_TYPE = "VariableType"
    REFERENCE_TYPE = "ReferenceType"
    DATA_TYPE = "DataType"
    UNKNOWN = "Unknown"


class OperationType(Enum):
    """Types of OPC UA operations."""
    READ = "Read"
    WRITE = "Write"
    CALL = "Call"
    BROWSE = "Browse"
    SUBSCRIBE = "Subscribe"


class OperationResult(Enum):
    """Result of an OPC UA operation."""
    SUCCESS = "Success"
    FAILURE = "Failure"


@dataclass
class ServerInfo:
    """Represents an OPC UA server entry."""
    name: str
    url: str
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    security_policy: str = "None"
    username: str = ""
    password: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "security_policy": self.security_policy,
            "username": self.username,
            "password": self.password,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ServerInfo":
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            security_policy=data.get("security_policy", "None"),
            username=data.get("username", ""),
            password=data.get("password", ""),
        )


@dataclass
class NodeInfo:
    """Represents information about a browsed OPC UA node."""
    node_id: str
    browse_name: str
    display_name: str
    node_class: NodeType = NodeType.UNKNOWN
    description: str = ""
    write_mask: int = 0
    user_write_mask: int = 0
    # Variable-specific
    value: Any = None
    data_type: str = ""
    # Method-specific
    executable: bool = False
    user_executable: bool = False
    event_notifier: int = 0


@dataclass
class FavoriteItem:
    """A favorited OPC UA node."""
    display_name: str
    node_id: str
    node_type: NodeType
    server_url: str = ""
    server_name: str = ""
    input_args: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "display_name": self.display_name,
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "server_url": self.server_url,
            "server_name": self.server_name,
            "input_args": self.input_args,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FavoriteItem":
        return cls(
            display_name=data.get("display_name", ""),
            node_id=data.get("node_id", ""),
            node_type=NodeType(data.get("node_type", "Unknown")),
            server_url=data.get("server_url", ""),
            server_name=data.get("server_name", ""),
            input_args=data.get("input_args", []),
        )


@dataclass
class HistoryEntry:
    """A logged operation in the operation history."""
    timestamp: datetime
    server_name: str
    node_id: str
    operation: OperationType
    result: OperationResult
    value: str = ""

    @property
    def time_str(self) -> str:
        return self.timestamp.strftime("%H:%M:%S")


@dataclass
class MethodArgument:
    """Represents an input/output argument of an OPC UA method."""
    name: str
    data_type: str
    description: str = ""
    value: Any = None
