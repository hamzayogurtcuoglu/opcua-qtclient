"""Generic, JSON-configured live-data engine for the 3D Scene Builder.

A scene can carry a list of ``dataSources`` (plain JSON, shipped inside the
scene file). Each source describes an OPC UA method/variable to poll and how to
map its result onto scene *anchors* — named positions in the scene. The engine
is completely generic: it has no knowledge of any specific server. All
scenario knowledge lives in the JSON config, so anyone can add a source without
touching Python.

Source config (flat array example)::

    {
      "id": "items",
      "endpoint": "opc.tcp://host:port/",
      "object": "MyObject",                  # OPC UA object (display name)
      "method": "GetItems",                  # method to call
      "args": [],
      "parse": "json",                       # result string -> JSON
      "items": "items",                      # path to the array
      "vars": {                              # extract fields per item
        "a": "position.0", "b": "position.1",
        "c": "position.2", "occ": "exists"
      },
      "key": "{a}/{b}/{c}",                  # anchor key built from vars
      "on": "occ"                            # truthy -> present
    }

Nested example (method-call chain) uses ``collect`` steps::

    "collect": [
      {"eachKey": "Group*", "as": "group", "strip": "Group"},
      {"into": "items"},
      {"eachKey": "*", "as": "item"},
      {"subcall": {"object": "MyObject", "method": "GetDetails",
                   "args": ["{group}", "{item}"], "parse": "json"}},
      {"each": "slots", "vars": {"slot": "slot_number", "occ": "uid"}}
    ]

The engine returns ``{source_id: {anchor_key: bool}}`` which the view turns into
markers appearing/disappearing at the matching anchors.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional

from asyncua import Client

logger = logging.getLogger(__name__)

# Errors that mean the socket/session died and we must reconnect.
_CONN_ERRORS = (ConnectionError, OSError, asyncio.TimeoutError,
                asyncio.IncompleteReadError)


def _is_conn_error(exc: Exception) -> bool:
    if isinstance(exc, _CONN_ERRORS):
        return True
    name = type(exc).__name__
    return any(k in name for k in (
        "Connection", "Timeout", "Disconnect", "SecureChannel", "SessionId",
        "Socket",
    ))


# ── small helpers ────────────────────────────────────────────────────────
def _parse_json(value: Any, default: Any) -> Any:
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if isinstance(value, str) and value:
        try:
            return json.loads(value)
        except ValueError:
            return default
    if isinstance(value, (dict, list)):
        return value
    return default


def _dig(obj: Any, path: str) -> Any:
    """Walk ``obj`` by a dotted path; numeric parts index into lists."""
    if path in ("", None):
        return obj
    cur = obj
    for part in str(path).split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, (list, tuple)):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


def _match(pattern: str, key: str) -> bool:
    if pattern in ("*", "", None):
        return True
    if pattern.endswith("*"):
        return str(key).startswith(pattern[:-1])
    return str(key) == pattern


def _fmt(template: str, vars: dict) -> str:
    def repl(m):
        return str(vars.get(m.group(1), ""))
    return re.sub(r"\{([^}]+)\}", repl, str(template))


def _coerce(text: Any) -> Any:
    if not isinstance(text, str):
        return text
    for caster in (int, float):
        try:
            return caster(text)
        except ValueError:
            continue
    return text


def _truthy(expr: str, row: dict) -> bool:
    if not expr:
        return True
    # Support "<var> == <lit>" / "<var> != <lit>"; else treat as a truthy field.
    for op in ("==", "!="):
        if op in expr:
            lhs, rhs = expr.split(op, 1)
            lv = row.get(lhs.strip())
            rv = rhs.strip().strip("'\"")
            rv_c = _coerce(rv)
            lv_c = _coerce(lv) if isinstance(lv, str) else lv
            equal = (str(lv_c) == str(rv_c)) or (lv_c == rv_c)
            return equal if op == "==" else not equal
    val = row.get(expr.strip())
    if isinstance(val, str):
        return val not in ("", "0", "false", "False")
    return bool(val)


async def _child_by_display_name(parent, name: str):
    for child in await parent.get_children():
        dn = await child.read_display_name()
        if dn.Text == name:
            return child
    raise LookupError(f"OPC UA child '{name}' not found")


# ── node-resolution cache ────────────────────────────────────────────────
# Browsing the address space (get_children + read_display_name on each child)
# to find an object/variable is expensive and was repeated on every poll for
# every variable. We cache the resolved Node per (object, child) on the client,
# so after the first poll lookups are free. The cache lives on the client, so a
# reconnect (new client) naturally starts fresh.
def _client_cache(client) -> dict:
    cache = getattr(client, "_scene_cache", None)
    if cache is None:
        cache = {}
        try:
            client._scene_cache = cache
        except Exception:
            pass
    return cache


async def _get_object(client: Client, object_name: str):
    cache = _client_cache(client)
    key = ("obj", object_name)
    node = cache.get(key)
    if node is None:
        node = await _child_by_display_name(client.nodes.objects, object_name)
        cache[key] = node
    return node


async def _get_child(client: Client, parent, parent_name: str, child_name: str):
    cache = _client_cache(client)
    key = ("child", parent_name, child_name)
    node = cache.get(key)
    if node is None:
        node = await _child_by_display_name(parent, child_name)
        cache[key] = node
    return node


async def _read_many(client: Client, nodes: list):
    """Read many node values in a single request (falls back to per-node)."""
    if not nodes:
        return []
    try:
        return await client.read_values(nodes)
    except Exception:
        out = []
        for n in nodes:
            try:
                out.append(await n.read_value())
            except Exception:
                out.append(None)
        return out


async def _call(client: Client, object_name: str, method_name: str, *args):
    parent = await _get_object(client, object_name)
    method = await _get_child(client, parent, object_name, method_name)
    result = await parent.call_method(method, *args)
    if isinstance(result, (list, tuple)) and result:
        return result[0]
    return result


async def _resolve_var(client: Client, object_name: str, variable_name: str):
    parent = await _get_object(client, object_name)
    return await _get_child(client, parent, object_name, variable_name)


async def _read_var(client: Client, object_name: str, variable_name: str):
    node = await _resolve_var(client, object_name, variable_name)
    return await node.read_value()


async def call_action(endpoint: str, object_name: str, method: str, args=None):
    """Open a short-lived client and invoke an OPC UA method (button actions)."""
    async with Client(endpoint, timeout=3) as client:
        return await _call(client, object_name, method, *(args or []))


def _map_color(m: dict, val) -> str:
    if isinstance(val, bool):
        keys = ["true" if val else "false"]
    else:
        keys = [str(val)]
    for k in keys:
        if k in m:
            return m[k]
    return m.get("default", "#6b7280")


# ── engine ───────────────────────────────────────────────────────────────
class LiveDataEngine:
    """Polls the configured ``dataSources`` and reports anchor occupancy."""

    def __init__(self, sources: list[dict]):
        self.sources = [s for s in (sources or []) if s.get("id")]
        # Persistent clients, one per endpoint, reused across polls. Opening a
        # fresh OPC UA connection (handshake + session + type loading) on every
        # poll is what made the scene feel frozen.
        self._clients: dict[str, Client] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def has_sources(self) -> bool:
        return bool(self.sources)

    async def _client_for(self, endpoint: str) -> Client:
        """Return a connected, reused client for ``endpoint`` (connect once)."""
        client = self._clients.get(endpoint)
        if client is not None:
            return client
        lock = self._locks.setdefault(endpoint, asyncio.Lock())
        async with lock:                       # avoid two concurrent connects
            client = self._clients.get(endpoint)
            if client is not None:
                return client
            client = Client(endpoint, timeout=4)
            await client.connect()
            # Custom structures only need loading once per connection, not per poll.
            try:
                await client.load_data_type_definitions()
            except Exception:
                pass
            self._clients[endpoint] = client
            return client

    async def _drop(self, endpoint: str):
        client = self._clients.pop(endpoint, None)
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass

    async def aclose(self):
        """Disconnect every persistent client (called when Live stops)."""
        for endpoint in list(self._clients):
            await self._drop(endpoint)

    async def read_single(self, endpoint: str, object_name: str, variable: str):
        """Read one variable (e.g. a configured poll-rate source)."""
        client = await self._client_for(endpoint)
        return await _read_var(client, object_name, variable)

    async def poll(self) -> dict:
        """Return ``{source_id: {anchor_key: bool}}`` (or None on failure)."""
        out: dict[str, Optional[dict]] = {}
        groups: dict[str, list] = {}
        for src in self.sources:
            groups.setdefault(src.get("endpoint", ""), []).append(src)
        for endpoint, srcs in groups.items():
            try:
                client = await self._client_for(endpoint)
            except Exception as exc:
                logger.debug("endpoint %s unreachable: %s", endpoint, exc)
                await self._drop(endpoint)
                for src in srcs:
                    out[src["id"]] = None
                continue
            for src in srcs:
                try:
                    out[src["id"]] = await self._eval(client, src)
                except Exception as exc:
                    out[src["id"]] = None
                    if _is_conn_error(exc):
                        # Socket/session died — drop it; the rest retry next poll.
                        logger.debug("connection lost on %s: %s", endpoint, exc)
                        await self._drop(endpoint)
                        for s in srcs:
                            out.setdefault(s["id"], None)
                        break
                    logger.debug("source %s failed: %s", src["id"], exc)
        return out

    async def _eval(self, client: Client, src: dict) -> dict:
        if src.get("render") == "racks":
            return await self._eval_racks(client, src)
        if src.get("render") == "color":
            return await self._eval_color(client, src)
        if src.get("render") == "panel":
            return await self._eval_panel(client, src)
        raw = await _call(client, src["object"], src["method"], *(src.get("args") or []))
        data = _parse_json(raw, {}) if src.get("parse") == "json" else raw
        rows: list[dict] = []
        if "collect" in src:
            await self._collect(client, data, src["collect"], {}, rows)
        else:
            items = _dig(data, src.get("items", "")) or []
            for el in items:
                row = {}
                for var, path in (src.get("vars") or {}).items():
                    row[var] = _dig(el, path)
                rows.append(row)
        present: dict[str, int] = {}
        for row in rows:
            key = _fmt(src.get("key", ""), row)
            # state 2 = occupied (tube), 1 = present but empty (marker/slot).
            present[key] = 2 if _truthy(src.get("on", ""), row) else 1
        return present

    async def _eval_racks(self, client: Client, src: dict) -> dict:
        """Return ``{region_key: {rack_id: {total, occ:[slots]}}}`` for racks.

        Combines an enumeration call (e.g. GetExistRacks → total slots per rack)
        with a per-rack details call (e.g. GetWorkPlace → occupied slots). All
        object/method names live in the JSON config.
        """
        raw = await _call(client, src["object"], src["method"], *(src.get("args") or []))
        data = _parse_json(raw, {}) if src.get("parse") == "json" else raw
        region_prefix = src.get("region", "")
        wp = src.get("workplace") or {}
        out: dict[str, dict] = {}
        for dkey, dval in (data or {}).items():
            if not _match(src.get("drawers", "*"), dkey):
                continue
            drawer = str(dkey).replace("Drawer", "")
            racks = _dig(dval, src.get("racksPath", "racks")) or {}
            region = {}
            for rid, rinfo in (racks.items() if isinstance(racks, dict) else []):
                total = int(_dig(rinfo, src.get("totalField", "total_slots")) or 0)
                occ: list[int] = []
                try:
                    wraw = await _call(client, wp.get("object", src["object"]),
                                       wp.get("method"), _coerce(drawer), _coerce(rid))
                    wdata = _parse_json(wraw, {}) if wp.get("parse") == "json" else wraw
                    for s in (_dig(wdata, src.get("slotsPath", "slots")) or []):
                        sn = _dig(s, src.get("slotField", "slot_number"))
                        uid = _dig(s, src.get("occField", "s_uuid"))
                        if sn is not None and str(uid or "") != "":
                            occ.append(int(sn))
                except Exception:
                    pass
                region[str(rid)] = {"total": total, "occ": occ}
            if region:
                out[f"{region_prefix}/{drawer}"] = region
        return out

    async def _eval_color(self, client: Client, src: dict) -> dict:
        """Return ``{tag: colorHex}`` — recolour tagged objects from variables.

        All variables are read in a single batched request (after the nodes are
        resolved once and cached), instead of one round-trip per variable.
        """
        reads = src.get("reads", [])
        nodes, valid = [], []
        for r in reads:
            try:
                nodes.append(await _resolve_var(client, r["object"], r["variable"]))
                valid.append(r)
            except Exception:
                pass
        values = await _read_many(client, nodes)
        out: dict[str, str] = {}
        for r, v in zip(valid, values):
            out[r["tag"]] = _map_color(r.get("map", {}), v)
        for r in reads:                       # unresolved -> default colour
            out.setdefault(r["tag"], _map_color(r.get("map", {}), None))
        return out

    async def _eval_panel(self, client: Client, src: dict) -> dict:
        """Return ``{"rows": [...]}`` for a status panel of module variables.

        Reads every module's variable in a single batched request.
        """
        items = src.get("items", [])
        nodes, positions = [], []
        for i, it in enumerate(items):
            try:
                nodes.append(await _resolve_var(client, it["object"], it["variable"]))
                positions.append(i)
            except Exception:
                pass
        values = await _read_many(client, nodes)
        by_item = {positions[p]: (values[p] if p < len(values) else None)
                   for p in range(len(positions))}
        rows = []
        for i, it in enumerate(items):
            v = by_item.get(i)
            if v is None:
                v = "?"
            entry = (it.get("map") or {}).get(str(v))
            if isinstance(entry, list) and len(entry) == 2:
                text, color = entry
            else:
                text, color = str(v), "#9ca3af"
            rows.append({"label": it["label"], "value": str(v),
                         "text": text, "color": color})
        return {"rows": rows}

    async def _collect(self, client, ctx, steps, vars, rows):
        if not steps:
            rows.append(dict(vars))
            return
        step, rest = steps[0], steps[1:]
        if "each" in step:
            for el in (_dig(ctx, step["each"]) or []):
                nv = dict(vars)
                for var, path in (step.get("vars") or {}).items():
                    nv[var] = _dig(el, path)
                await self._collect(client, el, rest, nv, rows)
        elif "eachKey" in step:
            for k, v in (ctx or {}).items():
                if not _match(step["eachKey"], k):
                    continue
                nv = dict(vars)
                if step.get("as"):
                    val = k.replace(step["strip"], "") if step.get("strip") else k
                    nv[step["as"]] = val
                await self._collect(client, v, rest, nv, rows)
        elif "into" in step:
            await self._collect(client, _dig(ctx, step["into"]) or {}, rest, vars, rows)
        elif "subcall" in step:
            sc = step["subcall"]
            args = [_coerce(_fmt(a, vars)) for a in (sc.get("args") or [])]
            raw = await _call(client, sc["object"], sc["method"], *args)
            res = _parse_json(raw, {}) if sc.get("parse") == "json" else raw
            await self._collect(client, res, rest, vars, rows)
        else:
            await self._collect(client, ctx, rest, vars, rows)
