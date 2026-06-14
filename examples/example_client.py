"""
Example OPC UA Client Script — for testing Script Runner

Usage examples:
  python example_client.py --host 127.0.0.1 --port 4840
  python example_client.py --host 127.0.0.1 --port 4841 --action read --node "ns=2;s=PLC_2/Data/Temperature"
  python example_client.py --host 127.0.0.1 --port 4840 --action call --verbose
"""

import argparse
import asyncio
import sys
from asyncua import Client, ua


# ─────────────────────────────────────────────────────────────────────────────
# CLI Arguments
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="OPC UA Example Client — reads variables and calls methods",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="OPC UA server hostname or IP (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=4840,
        help="OPC UA server port (default: 4840)"
    )
    parser.add_argument(
        "--action",
        type=str,
        default="read",
        choices=["read", "call", "write", "monitor"],
        help="Action to perform: read | call | write | monitor (default: read)"
    )
    parser.add_argument(
        "--node",
        type=str,
        default="",
        help="Optional: specific Node ID to read/write e.g. ns=2;i=5 (default: empty)"
    )
    parser.add_argument(
        "--value",
        type=str,
        default="",
        help="Value to write when action=write e.g. 42.0 (default: empty)"
    )
    parser.add_argument(
        "--monitor-seconds",
        type=int,
        default=10,
        help="Seconds to monitor when action=monitor (default: 10)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed info for every node/value (default: False)"
    )
    return parser


# ─────────────────────────────────────────────────────────────────────────────
# Core Actions
# ─────────────────────────────────────────────────────────────────────────────

async def action_read(client: Client, node_id: str, verbose: bool):
    """Read all data variables from the server (or a specific node)."""
    print("\n" + "═" * 60)
    print("  ACTION: READ")
    print("═" * 60)

    if node_id:
        # Read a specific node
        node = client.get_node(node_id)
        val = await node.read_value()
        name = (await node.read_display_name()).Text
        print(f"  {name} ({node_id}) = {val}")
    else:
        # Browse and read all variables under DeviceSet
        objects = client.nodes.objects
        await _browse_and_read(objects, depth=0, verbose=verbose)


async def _browse_and_read(node, depth: int, verbose: bool):
    """Recursively browse and print variable values."""
    try:
        children = await node.get_children()
    except Exception:
        return

    for child in children:
        try:
            name = (await child.read_display_name()).Text
            node_class = await child.read_node_class()

            if node_class.name == "Variable":
                val = await child.read_value()
                node_id = child.nodeid.to_string()
                indent = "  " * depth
                if verbose:
                    print(f"{indent}📊 {name:<30} = {val!r:<20}  [{node_id}]")
                else:
                    print(f"{indent}📊 {name}: {val}")
            elif node_class.name in ("Object", "ObjectType"):
                indent = "  " * depth
                print(f"{indent}📁 {name}/")
                await _browse_and_read(child, depth + 1, verbose)
        except Exception as e:
            if verbose:
                print(f"  [warn] Could not read child: {e}")


async def action_call(client: Client, verbose: bool):
    """Call the ReadStatus and Start methods."""
    print("\n" + "═" * 60)
    print("  ACTION: CALL METHODS")
    print("═" * 60)

    # Find the methods folder
    ns = await client.get_namespace_index("http://opcua.example.com/simulation/1")

    methods_path = [
        client.nodes.objects,
        f"ns={ns};s=DeviceSet",
    ]

    try:
        objects = client.nodes.objects
        device_set = await objects.get_child(f"{ns}:DeviceSet")
        plc = await device_set.get_child(f"{ns}:PLC_1")
        methods_folder = await plc.get_child(f"{ns}:Methods")

        children = await methods_folder.get_children()
        for method_node in children:
            method_name = (await method_node.read_display_name()).Text
            print(f"\n  ▶ Calling method: {method_name}")

            try:
                if method_name == "Start":
                    result = await plc.call_method(method_node, ua.Variant(0, ua.VariantType.Int32))
                elif method_name == "Stop":
                    result = await plc.call_method(method_node)
                elif method_name == "Reset":
                    result = await plc.call_method(method_node, ua.Variant(True, ua.VariantType.Boolean))
                elif method_name == "ReadStatus":
                    result = await plc.call_method(method_node)
                else:
                    result = await plc.call_method(method_node)

                print(f"    ✅ Result: {result}")
            except Exception as e:
                print(f"    ❌ Error: {e}")

    except Exception as e:
        print(f"  ❌ Could not find methods folder: {e}")
        print("  Hint: Make sure test_server.py is running on the target port.")


async def action_write(client: Client, node_id: str, value: str, verbose: bool):
    """Write a value to a specific node."""
    print("\n" + "═" * 60)
    print("  ACTION: WRITE")
    print("═" * 60)

    if not node_id:
        print("  ❌ No --node specified. Use --node 'ns=2;i=5' for example.")
        return

    node = client.get_node(node_id)
    name = (await node.read_display_name()).Text
    old_val = await node.read_value()
    print(f"  Node: {name} ({node_id})")
    print(f"  Current value: {old_val}")

    # Try to cast to current type
    try:
        if isinstance(old_val, bool):
            typed_val = value.lower() in ("true", "1", "yes")
        elif isinstance(old_val, int):
            typed_val = int(value)
        elif isinstance(old_val, float):
            typed_val = float(value)
        else:
            typed_val = value

        vt = await node.read_data_type_as_variant_type()
        await node.write_value(ua.DataValue(ua.Variant(typed_val, vt)))
        new_val = await node.read_value()
        print(f"  ✅ Written: {typed_val!r}  →  New value: {new_val}")
    except Exception as e:
        print(f"  ❌ Write failed: {e}")


async def action_monitor(client: Client, seconds: int, verbose: bool):
    """Subscribe to data changes and print updates."""
    print("\n" + "═" * 60)
    print(f"  ACTION: MONITOR (for {seconds} seconds)")
    print("═" * 60)

    from asyncua import ua

    class DataChangeHandler:
        def datachange_notification(self, node, val, data):
            nid = node.nodeid.to_string()
            print(f"  🔔 Change  {nid:<28}  =  {val}")

    handler = DataChangeHandler()

    try:
        ns = await client.get_namespace_index("http://opcua.example.com/simulation/1")
        objects = client.nodes.objects
        device_set = await objects.get_child(f"{ns}:DeviceSet")
        plc = await device_set.get_child(f"{ns}:PLC_1")
        data_folder = await plc.get_child(f"{ns}:Data")
        variables = await data_folder.get_children()
    except Exception as e:
        print(f"  ❌ Could not browse data folder: {e}")
        return

    sub = await client.create_subscription(500, handler)

    watch_nodes = []
    for var in variables:
        try:
            nc = await var.read_node_class()
            if nc.name == "Variable":
                watch_nodes.append(var)
                n = (await var.read_display_name()).Text
                print(f"  👁  Watching: {n}")
        except Exception:
            pass

    await sub.subscribe_data_change(watch_nodes)
    print(f"\n  Monitoring... (Ctrl+C to stop early)\n")

    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        pass

    await sub.unsubscribe(watch_nodes)
    await sub.delete()
    print("\n  Monitoring complete.")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    parser = build_parser()
    args = parser.parse_args()

    url = f"opc.tcp://{args.host}:{args.port}/freeopcua/server/"
    print(f"Connecting to: {url}")

    try:
        async with Client(url=url) as client:
            print(f"✅ Connected!\n")

            if args.verbose:
                print(f"  Server URI : {await client.get_namespace_array()}")

            if args.action == "read":
                await action_read(client, args.node, args.verbose)
            elif args.action == "call":
                await action_call(client, args.verbose)
            elif args.action == "write":
                await action_write(client, args.node, args.value, args.verbose)
            elif args.action == "monitor":
                await action_monitor(client, args.monitor_seconds, args.verbose)

    except Exception as e:
        print(f"\n❌ Connection failed: {e}", file=sys.stderr)
        print("   Make sure test_server.py is running.", file=sys.stderr)
        sys.exit(1)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
