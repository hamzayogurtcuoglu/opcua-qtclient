"""Example OPC UA Test Server.

Creates a server at opc.tcp://localhost:4840 with:
- DeviceSet > PLC1 > Data (Temperature, Pressure, Speed, State variables)
- DeviceSet > PLC1 > Methods (Start, Stop, Reset methods)
- DeviceSet > PLC1 > Alarms folder

Variables update with simulated values every second.
"""

import asyncio
import logging
import random
import math
from datetime import datetime

from asyncua import Server, ua

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_server")
logger.setLevel(logging.INFO)


async def start_method(parent, start_type: ua.Int32 = 0):
    """Start method — simulates starting a device."""
    logger.info(f"▶ Start called with StartType={start_type}")
    return [ua.Variant(f"Started at {datetime.now().strftime('%H:%M:%S')}", ua.VariantType.String)]


async def stop_method(parent):
    """Stop method — simulates stopping a device."""
    logger.info("⏹ Stop called")
    return [ua.Variant("Stopped", ua.VariantType.String)]


async def reset_method(parent, reset_counters: ua.Boolean = True):
    """Reset method — simulates resetting a device."""
    logger.info(f"🔄 Reset called with ResetCounters={reset_counters}")
    return [ua.Variant("Reset complete", ua.VariantType.String)]


async def run_server(port, name, server_id=1):
    # ── Create Server ──
    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://0.0.0.0:{port}/freeopcua/server/")
    server.set_server_name(name)

    # Set security policies (allow no-security for easy testing)
    server.set_security_policy(
        [
            ua.SecurityPolicyType.NoSecurity,
        ]
    )

    # ── Namespace ──
    uri = f"http://opcua.example.com/simulation/{server_id}"
    ns = await server.register_namespace(uri)

    # ── Build Address Space ──
    objects = server.nodes.objects

    # DeviceSet folder
    device_set = await objects.add_folder(ns, "DeviceSet")

    # PLC folder
    plc = await device_set.add_folder(ns, f"PLC_{server_id}")

    # ── Data Variables ──
    data_folder = await plc.add_folder(ns, "Data")

    temperature = await data_folder.add_variable(
        ns, "Temperature", 23.7 + server_id, varianttype=ua.VariantType.Double
    )
    await temperature.set_writable()

    pressure = await data_folder.add_variable(
        ns, "Pressure", 5.2 + (server_id * 0.1), varianttype=ua.VariantType.Double
    )
    await pressure.set_writable()

    speed = await data_folder.add_variable(
        ns, "Speed", 1500.0 + (server_id * 100), varianttype=ua.VariantType.Double
    )
    await speed.set_writable()

    state = await data_folder.add_variable(
        ns, "State", True, varianttype=ua.VariantType.Boolean
    )
    await state.set_writable()

    motor_current = await data_folder.add_variable(
        ns, "MotorCurrent", 12.5 + server_id, varianttype=ua.VariantType.Double
    )
    await motor_current.set_writable()

    counter = await data_folder.add_variable(
        ns, "ProductionCounter", ua.Variant(0, ua.VariantType.Int32)
    )
    await counter.set_writable()

    error_code = await data_folder.add_variable(
        ns, "ErrorCode", ua.Variant(0, ua.VariantType.Int32)
    )
    await error_code.set_writable()

    device_name = await data_folder.add_variable(
        ns, "DeviceName", f"Simulation PLC {server_id}", varianttype=ua.VariantType.String
    )
    await device_name.set_writable()

    # ── Methods ──
    methods_folder = await plc.add_folder(ns, "Methods")

    # Start method with input argument
    start_arg = ua.Argument()
    start_arg.Name = "StartType"
    start_arg.DataType = ua.NodeId(ua.ObjectIds.Int32)
    start_arg.ValueRank = -1
    start_arg.Description = ua.LocalizedText("Start type: 0=Normal, 1=Quick, 2=Scheduled")

    start_output = ua.Argument()
    start_output.Name = "Result"
    start_output.DataType = ua.NodeId(ua.ObjectIds.String)
    start_output.ValueRank = -1
    start_output.Description = ua.LocalizedText("Start result message")

    await methods_folder.add_method(
        ns, "Start", start_method, [start_arg], [start_output]
    )

    # Stop method (no args)
    stop_output = ua.Argument()
    stop_output.Name = "Result"
    stop_output.DataType = ua.NodeId(ua.ObjectIds.String)
    stop_output.ValueRank = -1
    stop_output.Description = ua.LocalizedText("Stop result message")

    await methods_folder.add_method(
        ns, "Stop", stop_method, [], [stop_output]
    )

    # Reset method
    reset_arg = ua.Argument()
    reset_arg.Name = "ResetCounters"
    reset_arg.DataType = ua.NodeId(ua.ObjectIds.Boolean)
    reset_arg.ValueRank = -1
    reset_arg.Description = ua.LocalizedText("Whether to reset production counters")

    reset_output = ua.Argument()
    reset_output.Name = "Result"
    reset_output.DataType = ua.NodeId(ua.ObjectIds.String)
    reset_output.ValueRank = -1
    reset_output.Description = ua.LocalizedText("Reset result message")

    await methods_folder.add_method(
        ns, "Reset", reset_method, [reset_arg], [reset_output]
    )

    # ReadStatus method (no input, returns status string)
    async def read_status_method(parent):
        running = await state.read_value()
        temp = await temperature.read_value()
        cnt = await counter.read_value()
        return [ua.Variant(
            f"Running={running}, Temp={temp:.1f}C, Counter={cnt}",
            ua.VariantType.String
        )]

    status_output = ua.Argument()
    status_output.Name = "StatusReport"
    status_output.DataType = ua.NodeId(ua.ObjectIds.String)
    status_output.ValueRank = -1
    status_output.Description = ua.LocalizedText("Current device status summary")

    await methods_folder.add_method(
        ns, "ReadStatus", read_status_method, [], [status_output]
    )

    # ── Alarms folder ──
    alarms_folder = await plc.add_folder(ns, "Alarms")
    alarm_active = await alarms_folder.add_variable(
        ns, "HighTempAlarm", False, varianttype=ua.VariantType.Boolean
    )

    alarm_pressure = await alarms_folder.add_variable(
        ns, "LowPressureAlarm", False, varianttype=ua.VariantType.Boolean
    )

    # ── System folder ──
    system_folder = await plc.add_folder(ns, "System")
    uptime = await system_folder.add_variable(
        ns, "Uptime", 0.0, varianttype=ua.VariantType.Double
    )

    firmware = await system_folder.add_variable(
        ns, "FirmwareVersion", "v2.4.1", varianttype=ua.VariantType.String
    )

    serial_number = await system_folder.add_variable(
        ns, "SerialNumber", "SIM-PLC-2024-001", varianttype=ua.VariantType.String
    )

    # ── Start Server ──
    print(f"  [{name}] Started at opc.tcp://localhost:{port}/freeopcua/server/")

    async with server:
        t = 0
        count = 0
        while True:
            await asyncio.sleep(1)
            t += 1

            # Simulate sensor values with realistic patterns
            is_running = await state.read_value()

            if is_running:
                # Temperature: oscillates around 23-28°C
                temp_val = 25.0 + 3.0 * math.sin(t * 0.05) + random.gauss(0, 0.3)
                await temperature.write_value(round(temp_val, 1))

                # Pressure: oscillates around 4.5-6.0 bar
                press_val = 5.2 + 0.8 * math.sin(t * 0.03) + random.gauss(0, 0.1)
                await pressure.write_value(round(press_val, 1))

                # Speed: around 1500 RPM with noise
                speed_val = 1500.0 + 50 * math.sin(t * 0.1) + random.gauss(0, 10)
                await speed.write_value(round(speed_val, 1))

                # Motor current
                curr_val = 12.5 + 2.0 * math.sin(t * 0.07) + random.gauss(0, 0.5)
                await motor_current.write_value(round(curr_val, 1))

                # Production counter increments every ~5 seconds
                if t % 5 == 0:
                    count += 1
                    await counter.write_value(ua.Variant(count, ua.VariantType.Int32))

                # Alarms
                await alarm_active.write_value(temp_val > 27.5)
                await alarm_pressure.write_value(press_val < 4.8)

            # Uptime always increments
            await uptime.write_value(float(t))

            # Log every 10 seconds
            if t % 10 == 0:
                temp_now = await temperature.read_value()
                press_now = await pressure.read_value()
                logger.info(
                    f"[Sim] t={t}s | Temp={temp_now} | "
                    f"Pressure={press_now} | Running={is_running} | "
                    f"Counter={count}"
                )


if __name__ == "__main__":
    async def main():
        print("=" * 60)
        print("  Starting 3 OPC UA Simulation Servers...")
        print("  Server 1: opc.tcp://localhost:4840/freeopcua/server/")
        print("  Server 2: opc.tcp://localhost:4841/freeopcua/server/")
        print("  Server 3: opc.tcp://localhost:4842/freeopcua/server/")
        print("=" * 60)
        
        await asyncio.gather(
            run_server(4840, "Simulation Server 1", server_id=1),
            run_server(4841, "Simulation Server 2", server_id=2),
            run_server(4842, "Simulation Server 3", server_id=3),
        )

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServers stopped.")
