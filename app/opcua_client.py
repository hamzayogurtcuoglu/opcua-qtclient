"""Async OPC UA client wrapper using asyncua library."""

import asyncio
import logging
from typing import Any, Optional

from asyncua import Client, ua, Node
from asyncua.common.subscription import Subscription
from PyQt6.QtCore import QObject, pyqtSignal

from app.models import (
    ConnectionStatus, NodeInfo, NodeType, MethodArgument,
    OperationType, OperationResult, HistoryEntry,
)
from datetime import datetime

logger = logging.getLogger(__name__)


def _node_class_to_type(node_class: ua.NodeClass) -> NodeType:
    """Convert asyncua NodeClass to our NodeType enum."""
    mapping = {
        ua.NodeClass.Object: NodeType.OBJECT,
        ua.NodeClass.Variable: NodeType.VARIABLE,
        ua.NodeClass.Method: NodeType.METHOD,
        ua.NodeClass.View: NodeType.VIEW,
        ua.NodeClass.ObjectType: NodeType.OBJECT_TYPE,
        ua.NodeClass.VariableType: NodeType.VARIABLE_TYPE,
        ua.NodeClass.ReferenceType: NodeType.REFERENCE_TYPE,
        ua.NodeClass.DataType: NodeType.DATA_TYPE,
    }
    return mapping.get(node_class, NodeType.UNKNOWN)


class OpcUaClient(QObject):
    """Asynchronous OPC UA client with Qt signal integration.

    Wraps asyncua.Client and emits Qt signals for UI updates.
    All OPC UA operations are async and should be called via asyncio.
    """

    # Signals
    connection_changed = pyqtSignal(str, ConnectionStatus)  # url, status
    error_occurred = pyqtSignal(str, str)  # operation, error_message
    operation_logged = pyqtSignal(HistoryEntry)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._client: Optional[Client] = None
        self._url: str = ""
        self._status: ConnectionStatus = ConnectionStatus.DISCONNECTED
        self._subscription: Optional[Subscription] = None

    @property
    def url(self) -> str:
        return self._url

    @property
    def status(self) -> ConnectionStatus:
        return self._status

    @property
    def is_connected(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def _set_status(self, status: ConnectionStatus):
        self._status = status
        self.connection_changed.emit(self._url, status)

    def _log_operation(
        self, server_name: str, node_id: str,
        operation: OperationType, result: OperationResult, value: str = ""
    ):
        entry = HistoryEntry(
            timestamp=datetime.now(),
            server_name=server_name,
            node_id=node_id,
            operation=operation,
            result=result,
            value=value,
        )
        self.operation_logged.emit(entry)

    async def connect(
        self, url: str, security_policy: str = "None",
        username: str = "", password: str = ""
    ) -> bool:
        """Connect to an OPC UA server."""
        try:
            self._url = url
            self._set_status(ConnectionStatus.CONNECTING)

            actual_url = url.replace("localhost", "127.0.0.1")
            self._client = Client(url=actual_url)

            # Set security if needed
            if username and password:
                self._client.set_user(username)
                self._client.set_password(password)

            await self._client.connect()
            self._set_status(ConnectionStatus.CONNECTED)
            logger.info(f"Connected to {url}")
            return True

        except Exception as e:
            logger.error(f"Connection failed to {url}: {e}")
            self._set_status(ConnectionStatus.ERROR)
            self.error_occurred.emit("Connect", str(e))
            return False

    async def disconnect(self):
        """Disconnect from the current server."""
        if self._client:
            try:
                if self._subscription:
                    await self._subscription.delete()
                    self._subscription = None
                await self._client.disconnect()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self._client = None
                self._set_status(ConnectionStatus.DISCONNECTED)
                logger.info(f"Disconnected from {self._url}")

    def _get_node(self, node_id: str) -> Node:
        """Get a node object from its string ID."""
        if not self._client:
            raise RuntimeError("Not connected")
        return self._client.get_node(node_id)

    async def browse_node(self, node_id: str = "i=84") -> list[dict]:
        """Browse children of a node. Returns list of child info dicts.

        Args:
            node_id: The NodeId string. Defaults to "i=84" (Objects folder).

        Returns:
            List of dicts with keys: node_id, browse_name, display_name, node_class
        """
        if not self._client:
            return []

        try:
            node = self._get_node(node_id)
            children = await node.get_children()

            result = []
            for child in children:
                try:
                    browse_name = await child.read_browse_name()
                    display_name = await child.read_display_name()
                    node_class = await child.read_node_class()

                    result.append({
                        "node_id": child.nodeid.to_string(),
                        "browse_name": browse_name.to_string(),
                        "display_name": display_name.Text,
                        "node_class": _node_class_to_type(node_class),
                    })
                except Exception as e:
                    logger.warning(f"Error reading child node: {e}")
                    continue

            return result

        except Exception as e:
            logger.error(f"Browse failed for {node_id}: {e}")
            self.error_occurred.emit("Browse", str(e))
            return []

    async def read_node_attributes(self, node_id: str, server_name: str = "") -> NodeInfo:
        """Read all standard attributes of a node."""
        if not self._client:
            raise RuntimeError("Not connected")

        node = self._get_node(node_id)
        info = NodeInfo(node_id=node_id, browse_name="", display_name="")

        try:
            info.browse_name = (await node.read_browse_name()).to_string()
            info.display_name = (await node.read_display_name()).Text
            node_class = await node.read_node_class()
            info.node_class = _node_class_to_type(node_class)

            try:
                desc = await node.read_description()
                info.description = desc.Text if desc.Text else ""
            except Exception:
                info.description = ""

            try:
                info.write_mask = await node.read_attribute(ua.AttributeIds.WriteMask)
                info.write_mask = info.write_mask.Value.Value if info.write_mask.Value.Value else 0
            except Exception:
                info.write_mask = 0

            try:
                info.user_write_mask = await node.read_attribute(ua.AttributeIds.UserWriteMask)
                info.user_write_mask = info.user_write_mask.Value.Value if info.user_write_mask.Value.Value else 0
            except Exception:
                info.user_write_mask = 0

            # Method-specific attributes
            if info.node_class == NodeType.METHOD:
                try:
                    exec_attr = await node.read_attribute(ua.AttributeIds.Executable)
                    info.executable = bool(exec_attr.Value.Value)
                except Exception:
                    info.executable = False
                try:
                    user_exec = await node.read_attribute(ua.AttributeIds.UserExecutable)
                    info.user_executable = bool(user_exec.Value.Value)
                except Exception:
                    info.user_executable = False

            # Variable-specific attributes
            if info.node_class == NodeType.VARIABLE:
                try:
                    val = await node.read_value()
                    info.value = val
                    dt = await node.read_data_type_as_variant_type()
                    info.data_type = dt.name
                except Exception:
                    pass

            self._log_operation(
                server_name, node_id, OperationType.READ,
                OperationResult.SUCCESS, str(info.display_name)
            )

        except Exception as e:
            logger.error(f"Failed to read attributes for {node_id}: {e}")
            self.error_occurred.emit("Read Attributes", str(e))
            self._log_operation(
                server_name, node_id, OperationType.READ,
                OperationResult.FAILURE, str(e)
            )

        return info

    async def read_value(self, node_id: str, server_name: str = "") -> Any:
        """Read the current value of a variable node."""
        if not self._client:
            raise RuntimeError("Not connected")

        try:
            node = self._get_node(node_id)
            value = await node.read_value()
            self._log_operation(
                server_name, node_id, OperationType.READ,
                OperationResult.SUCCESS, str(value)
            )
            return value
        except Exception as e:
            logger.error(f"Read value failed for {node_id}: {e}")
            self.error_occurred.emit("Read Value", str(e))
            self._log_operation(
                server_name, node_id, OperationType.READ,
                OperationResult.FAILURE, str(e)
            )
            return None

    async def write_value(
        self, node_id: str, value: Any, data_type: str = "",
        server_name: str = ""
    ) -> bool:
        """Write a value to a variable node."""
        if not self._client:
            raise RuntimeError("Not connected")

        try:
            node = self._get_node(node_id)

            # Try to determine variant type from node if not specified
            vt = await node.read_data_type_as_variant_type()
            dv = ua.DataValue(ua.Variant(value, vt))
            await node.write_value(dv)

            self._log_operation(
                server_name, node_id, OperationType.WRITE,
                OperationResult.SUCCESS, str(value)
            )
            return True

        except Exception as e:
            logger.error(f"Write failed for {node_id}: {e}")
            self.error_occurred.emit("Write Value", str(e))
            self._log_operation(
                server_name, node_id, OperationType.WRITE,
                OperationResult.FAILURE, str(e)
            )
            return False

    async def call_method(
        self, parent_node_id: str, method_node_id: str,
        args: list = None, server_name: str = ""
    ) -> Any:
        """Call an OPC UA method on a parent object."""
        if not self._client:
            raise RuntimeError("Not connected")

        try:
            parent = self._get_node(parent_node_id)
            method = self._get_node(method_node_id)
            result = await parent.call_method(method, *(args or []))

            result_str = f"OutputArguments: {result}" if result else "OutputArguments: ()"
            self._log_operation(
                server_name, method_node_id, OperationType.CALL,
                OperationResult.SUCCESS, result_str
            )
            return result

        except Exception as e:
            logger.error(f"Method call failed for {method_node_id}: {e}")
            self.error_occurred.emit("Call Method", str(e))
            self._log_operation(
                server_name, method_node_id, OperationType.CALL,
                OperationResult.FAILURE, str(e)
            )
            return None

    async def get_method_arguments(self, method_node_id: str) -> tuple[list[MethodArgument], list[MethodArgument]]:
        """Get input and output argument definitions of a method.

        Returns:
            Tuple of (input_args, output_args)
        """
        if not self._client:
            return [], []

        try:
            method_node = self._get_node(method_node_id)
            children = await method_node.get_children()

            input_args = []
            output_args = []

            for child in children:
                browse_name = await child.read_browse_name()
                name = browse_name.Name

                if name == "InputArguments":
                    args = await child.read_value()
                    if args:
                        for arg in args:
                            input_args.append(MethodArgument(
                                name=arg.Name,
                                data_type=self._variant_type_name(arg.DataType),
                                description=arg.Description.Text if arg.Description and arg.Description.Text else "",
                            ))

                elif name == "OutputArguments":
                    args = await child.read_value()
                    if args:
                        for arg in args:
                            output_args.append(MethodArgument(
                                name=arg.Name,
                                data_type=self._variant_type_name(arg.DataType),
                                description=arg.Description.Text if arg.Description and arg.Description.Text else "",
                            ))

            return input_args, output_args

        except Exception as e:
            logger.error(f"Failed to get method arguments for {method_node_id}: {e}")
            return [], []

    def _variant_type_name(self, data_type_id) -> str:
        """Convert a DataType NodeId to a human-readable type name."""
        type_map = {
            ua.NodeId(ua.ObjectIds.Boolean): "Boolean",
            ua.NodeId(ua.ObjectIds.SByte): "SByte",
            ua.NodeId(ua.ObjectIds.Byte): "Byte",
            ua.NodeId(ua.ObjectIds.Int16): "Int16",
            ua.NodeId(ua.ObjectIds.UInt16): "UInt16",
            ua.NodeId(ua.ObjectIds.Int32): "Int32",
            ua.NodeId(ua.ObjectIds.UInt32): "UInt32",
            ua.NodeId(ua.ObjectIds.Int64): "Int64",
            ua.NodeId(ua.ObjectIds.UInt64): "UInt64",
            ua.NodeId(ua.ObjectIds.Float): "Float",
            ua.NodeId(ua.ObjectIds.Double): "Double",
            ua.NodeId(ua.ObjectIds.String): "String",
            ua.NodeId(ua.ObjectIds.DateTime): "DateTime",
            ua.NodeId(ua.ObjectIds.ByteString): "ByteString",
        }
        return type_map.get(data_type_id, str(data_type_id))

    async def discover_servers(self, discovery_url: str = "opc.tcp://localhost:4840") -> list[dict]:
        """Discover OPC UA servers using LDS."""
        try:
            client = Client(url=discovery_url)
            servers = await client.connect_and_find_servers()
            result = []
            for server in servers:
                urls = [url for url in (server.DiscoveryUrls or [])]
                result.append({
                    "name": server.ApplicationName.Text,
                    "urls": urls,
                    "uri": server.ApplicationUri,
                })
            return result
        except Exception as e:
            logger.error(f"Server discovery failed: {e}")
            self.error_occurred.emit("Discovery", str(e))
            return []

    async def get_parent_node_id(self, node_id: str) -> Optional[str]:
        """Get the parent node ID of a given node (for method calling context)."""
        if not self._client:
            return None
        try:
            node = self._get_node(node_id)
            parent = await node.get_parent()
            if parent:
                return parent.nodeid.to_string()
        except Exception:
            pass
        return None
