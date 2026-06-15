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

DEFAULT_REQUEST_TIMEOUT = 600.0
DEFAULT_WATCHDOG_INTERVAL = 600.0


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


class SubscriptionHandler:
    """Receives data change events for subscriptions."""
    def __init__(self, callback):
        self.callback = callback

    def datachange_notification(self, node: Node, val, data):
        """Called when a subscribed node's value changes."""
        self.callback(node.nodeid.to_string(), val)


class OpcUaClient(QObject):
    """Asynchronous OPC UA client with Qt signal integration.

    Wraps asyncua.Client and emits Qt signals for UI updates.
    All OPC UA operations are async and should be called via asyncio.
    """

    # Signals
    connection_changed = pyqtSignal(str, ConnectionStatus)  # url, status
    error_occurred = pyqtSignal(str, str)  # operation, error_message
    operation_logged = pyqtSignal(HistoryEntry)
    data_changed = pyqtSignal(str, str, object)  # node_id, display_name, value

    def __init__(
        self,
        parent: Optional[QObject] = None,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        watchdog_interval: float = DEFAULT_WATCHDOG_INTERVAL,
    ):
        super().__init__(parent)
        self._client: Optional[Client] = None
        self._url: str = ""
        self._status: ConnectionStatus = ConnectionStatus.DISCONNECTED
        self._nodes: dict[str, Node] = {}
        self._request_timeout = request_timeout
        self._watchdog_interval = watchdog_interval
        self._request_lock = asyncio.Lock()
        
        self._subscription: Optional[Subscription] = None
        self._sub_handler: Optional[SubscriptionHandler] = None
        self._monitored_nodes = {}  # node_id -> handle
        self._monitored_names = {}  # node_id -> name

    def _on_datachange(self, node_id: str, val: Any):
        name = self._monitored_names.get(node_id, node_id)
        self.data_changed.emit(node_id, name, val)

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

    def _create_client(self, url: str, timeout: float | None = None) -> Client:
        request_timeout = timeout or self._request_timeout
        try:
            return Client(
                url=url,
                timeout=request_timeout,
                watchdog_intervall=self._watchdog_interval,
            )
        except TypeError:
            client = Client(url=url, timeout=request_timeout)
            if hasattr(client, "watchdog_intervall"):
                setattr(client, "watchdog_intervall", self._watchdog_interval)
            return client

    def _apply_request_timeout_patch(self) -> None:
        """Make high-level service calls honour the configured request timeout.

        asyncua hardcodes a 1-second per-request timeout for high-level service
        calls (read/write/call) because ``UaClient._send_request`` /
        ``Session._send_request`` default ``timeout`` to ``1`` instead of
        ``None``. That value is passed straight through and *overrides* the
        ``Client(timeout=...)`` we configured, so a method like Configure that
        takes longer than 1 s to return is cancelled after ~1 s and surfaces as
        "Unhandled exception while sending request to OPC UA server" /
        "Future for request id N is already done".

        We wrap ``uaclient._send_request`` so that the library's default
        sentinel of ``1`` falls back to ``None`` -- which makes the socket layer
        use the protocol's configured timeout (``request_timeout``). Callers that
        pass an explicit timeout are left untouched.
        """
        client = self._client
        uaclient = getattr(client, "uaclient", None) if client else None
        if uaclient is None:
            return
        original = getattr(uaclient, "_send_request", None)
        if original is None or getattr(uaclient, "_request_timeout_patched", False):
            return

        async def _send_request(request, timeout=1, message_type=ua.MessageType.SecureMessage):
            if timeout == 1:
                # Library default -> use the protocol's configured timeout.
                timeout = None
            return await original(request, timeout, message_type)

        try:
            uaclient._send_request = _send_request  # type: ignore[assignment]
            uaclient._request_timeout_patched = True  # type: ignore[attr-defined]
        except Exception:
            logger.debug("Could not apply request-timeout patch", exc_info=True)

    @staticmethod
    def _describe_exception(exc: BaseException) -> str:
        """Build a message that unwraps asyncua's generic wrapper.

        asyncua re-raises socket/timeout failures as a bare
        'Unhandled exception while sending request to OPC UA server', hiding the
        real cause behind ``__cause__``. Surface the underlying chain so the
        actual failure (TimeoutError, ConnectionResetError, ServiceFault, ...)
        is visible in logs and the UI.
        """
        parts = []
        seen = set()
        current: Optional[BaseException] = exc
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            text = str(current).strip()
            label = type(current).__name__
            parts.append(f"{label}: {text}" if text else label)
            current = current.__cause__ or current.__context__
        return " <- ".join(parts)

    def _is_transport_error(self, exc: BaseException) -> bool:
        message = self._describe_exception(exc).lower()
        return (
            isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError))
            or "connection" in message
            or "sending request" in message
            or "timeout" in message
            or "already done" in message
            or "is closed" in message
        )

    def _mark_transport_error(self, exc: Exception):
        if self._is_transport_error(exc):
            self._set_status(ConnectionStatus.ERROR)

    async def connect(
        self, url: str, security_policy: str = "None",
        username: str = "", password: str = "", timeout: float = 10.0
    ) -> bool:
        """Connect to an OPC UA server."""
        try:
            self._url = url
            self._set_status(ConnectionStatus.CONNECTING)

            actual_url = url.replace("localhost", "127.0.0.1")
            self._client = self._create_client(actual_url)

            # Set security if needed
            if username and password:
                self._client.set_user(username)
                self._client.set_password(password)

            # auto_reconnect lets asyncua's supervisor re-establish the channel/session
            # (and re-create subscriptions) if the server drops the connection while a
            # long-running method like Configure is executing. Fall back gracefully on
            # older asyncua versions that do not support the keyword.
            try:
                await asyncio.wait_for(
                    self._client.connect(auto_reconnect=True), timeout=timeout
                )
            except TypeError:
                await asyncio.wait_for(self._client.connect(), timeout=timeout)
            self._apply_request_timeout_patch()
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
            async with self._request_lock:
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
            self._mark_transport_error(e)
            self.error_occurred.emit("Browse", str(e))
            return []

    async def read_node_attributes(self, node_id: str, server_name: str = "") -> NodeInfo:
        """Read all standard attributes of a node."""
        if not self._client:
            raise RuntimeError("Not connected")

        info = NodeInfo(node_id=node_id, browse_name="", display_name="")

        try:
            async with self._request_lock:
                node = self._get_node(node_id)
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
            self._mark_transport_error(e)
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
            async with self._request_lock:
                node = self._get_node(node_id)
                value = await node.read_value()
            self._log_operation(
                server_name, node_id, OperationType.READ,
                OperationResult.SUCCESS, str(value)
            )
            return value
        except Exception as e:
            logger.error(f"Read value failed for {node_id}: {e}")
            self._mark_transport_error(e)
            self.error_occurred.emit("Read Value", str(e))
            self._log_operation(
                server_name, node_id, OperationType.READ,
                OperationResult.FAILURE, str(e)
            )
            return None

    async def subscribe_node(self, node_id: str, node_name: str = "", period: int = 500) -> bool:
        """Subscribe to data changes for a node."""
        if not self._client:
            return False
        try:
            async with self._request_lock:
                if not self._subscription:
                    self._sub_handler = SubscriptionHandler(self._on_datachange)
                    self._subscription = await self._client.create_subscription(period, self._sub_handler)

                node = self._get_node(node_id)
                handle = await self._subscription.subscribe_data_change(node)
            self._monitored_nodes[node_id] = handle
            self._monitored_names[node_id] = node_name or node_id
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to {node_id}: {e}")
            self._mark_transport_error(e)
            self.error_occurred.emit("Subscribe", str(e))
            return False

    async def unsubscribe_node(self, node_id: str) -> bool:
        """Unsubscribe from data changes for a node."""
        if not self._subscription or node_id not in self._monitored_nodes:
            return False
        try:
            async with self._request_lock:
                handle = self._monitored_nodes.pop(node_id)
                await self._subscription.unsubscribe(handle)
            return True
        except Exception as e:
            logger.error(f"Failed to unsubscribe from {node_id}: {e}")
            self._mark_transport_error(e)
            return False

    async def write_value(
        self, node_id: str, value: Any, data_type: str = "",
        server_name: str = ""
    ) -> bool:
        """Write a value to a variable node."""
        if not self._client:
            raise RuntimeError("Not connected")

        try:
            async with self._request_lock:
                node = self._get_node(node_id)

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
            self._mark_transport_error(e)
            self.error_occurred.emit("Write Value", str(e))
            self._log_operation(
                server_name, node_id, OperationType.WRITE,
                OperationResult.FAILURE, str(e)
            )
            return False

    async def _invoke_method(self, parent_node_id: str, method_node_id: str, args: list):
        async with self._request_lock:
            parent = self._get_node(parent_node_id)
            method = self._get_node(method_node_id)
            return await parent.call_method(method, *(args or []))

    async def call_method(
        self, parent_node_id: str, method_node_id: str,
        args: list = None, server_name: str = ""
    ) -> Any:
        """Call an OPC UA method on a parent object.

        If the first attempt fails because the server dropped the connection
        while executing the method (a single-threaded server cannot answer the
        supervisor's keep-alive probe meanwhile), give asyncua's auto-reconnect
        supervisor a moment to restore the channel and retry once.
        """
        if not self._client:
            raise RuntimeError("Not connected")

        last_error: Optional[Exception] = None
        for attempt in range(2):
            try:
                result = await self._invoke_method(parent_node_id, method_node_id, args)
                result_str = f"OutputArguments: {result}" if result else "OutputArguments: ()"
                self._log_operation(
                    server_name, method_node_id, OperationType.CALL,
                    OperationResult.SUCCESS, result_str
                )
                return result
            except Exception as e:
                last_error = e
                detail = self._describe_exception(e)
                if attempt == 0 and self._is_transport_error(e):
                    logger.warning(
                        "Method call %s hit a transport error (%s); "
                        "waiting for reconnect and retrying once",
                        method_node_id, detail,
                    )
                    if await self._await_reconnect():
                        continue
                logger.error(
                    "Method call failed for %s: %s", method_node_id, detail
                )
                break

        self._mark_transport_error(last_error)
        detail = self._describe_exception(last_error)
        self.error_occurred.emit("Call Method", detail)
        self._log_operation(
            server_name, method_node_id, OperationType.CALL,
            OperationResult.FAILURE, detail
        )
        return None

    async def _await_reconnect(self, timeout: float = 15.0) -> bool:
        """Wait until asyncua reports the session reconnected, up to ``timeout``.

        Returns True if the client looks usable again, False otherwise.
        """
        client = self._client
        if client is None:
            return False
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            try:
                uaclient = getattr(client, "uaclient", None)
                state = getattr(uaclient, "state", None)
                state_name = getattr(state, "name", str(state))
                if state is None or state_name == "CONNECTED":
                    return True
            except Exception:
                return True
            await asyncio.sleep(0.5)
        return False

    async def get_method_arguments(self, method_node_id: str) -> tuple[list[MethodArgument], list[MethodArgument]]:
        """Get input and output argument definitions of a method.

        Returns:
            Tuple of (input_args, output_args)
        """
        if not self._client:
            return [], []

        try:
            async with self._request_lock:
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
            self._mark_transport_error(e)
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

    async def discover_servers(self, discovery_url: str = "opc.tcp://localhost:4840", timeout: float = 3.0) -> list[dict]:
        """Discover OPC UA servers using LDS."""
        try:
            client = self._create_client(discovery_url, timeout=timeout)
            servers = await asyncio.wait_for(client.connect_and_find_servers(), timeout=timeout)
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

    async def probe_server(self, endpoint_url: str, timeout: float = 3.0) -> Optional[dict]:
        """Return a fallback server entry when a port accepts a normal OPC UA session."""
        client = self._create_client(endpoint_url, timeout=timeout)
        try:
            await asyncio.wait_for(client.connect(), timeout=timeout)
            name = "OPC UA Server"
            try:
                display_name = await asyncio.wait_for(
                    client.nodes.server.read_display_name(),
                    timeout=timeout,
                )
                if display_name.Text:
                    name = display_name.Text
            except Exception:
                pass

            return {"name": name, "urls": [endpoint_url], "uri": endpoint_url}
        except Exception:
            return None
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    async def get_parent_node_id(self, node_id: str) -> Optional[str]:
        """Get the parent node ID of a given node (for method calling context)."""
        if not self._client:
            return None
        try:
            async with self._request_lock:
                node = self._get_node(node_id)
                parent = await node.get_parent()
            if parent:
                return parent.nodeid.to_string()
        except Exception:
            pass
        return None
