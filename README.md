# OPC UA Client (PyQt6 & asyncua)

A modern, high-performance, asynchronous OPC UA Client built with Python, PyQt6, and the `asyncua` (FreeOpcUa) library.

This application provides a comprehensive UI to connect to OPC UA servers, browse their address spaces, read/write variables, call methods, execute custom Python scripts against the server, and manage your frequent connections and nodes via a Favorites system.

## 🚀 Features

- **Modern & Responsive UI**: Built with PyQt6, featuring fully responsive layouts, dockable widgets, and a clean user experience.
- **Dark & Light Mode**: Seamlessly switch between a sleek Dark Mode and a crisp Light Mode.
- **Address Space Browsing**: Navigate through complex OPC UA object trees asynchronously without freezing the UI.
- **Read & Write Variables**: Easily inspect the attributes of any node, and write new values to Variables using appropriate OPC UA Variant types.
- **Method Execution**: 
  - Call OPC UA methods directly from the UI.
  - Arguments are automatically parsed, and input fields are generated dynamically based on expected types.
  - Run methods instantly from your "Favorites" list with auto-connect functionality.
- **Python Script Runner**: 
  - Write and execute custom Python scripts against the connected OPC UA server.
  - Automatically receives the `client` and `node` context.
  - Save scripts to Favorites for one-click execution.
- **Favorites Management**:
  - Save your most used servers, variables, methods, and scripts to the floating "Favorites" dock.
  - Click a favorite to instantly connect to its server and jump to or execute the saved node.
- **Export/Import Configuration**:
  - Save your entire workspace (servers, favorites, and settings) into a single JSON file.
  - Easily share your configuration across different machines or environments.
- **Data Management**: Quickly wipe all saved data or clear favorites with built-in data management tools.

## 🛠 Prerequisites

- **Python 3.10+**
- **macOS / Linux / Windows**

## 📦 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/hamzayogurtcuoglu/opcua-qtclient.git
   cd opcua-qtclient
   ```

2. **Create a virtual environment (Recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Ensure your `requirements.txt` contains `PyQt6`, `asyncua`, `qasync`.)*

## 🎮 Usage

### 1. Start the OPC UA Client
```bash
python main.py
```

### 2. Testing with the Local Server
If you don't have a real OPC UA server to connect to, you can run the provided test server which generates dummy data and methods.

Open a new terminal window, activate your virtual environment, and run:
```bash
python test_server.py
```
*This starts a simulation server at `opc.tcp://127.0.0.1:4840/freeopcua/server/`.*

### 3. Connect and Explore
1. In the client UI, click **+ Add Server**.
2. Enter a Name (e.g., `Local Sim`) and the URL `opc.tcp://127.0.0.1:4840/freeopcua/server/`.
3. Select the server from the left sidebar and click **Connect**.
4. Browse the `Objects` folder to find the simulated variables and methods.

## 📁 Project Structure

- `main.py`: Entry point for the application. Sets up the QAsync event loop.
- `test_server.py`: A script providing a simulated OPC UA server for testing.
- `app/`: Main application package.
  - `main_window.py`: The core UI orchestrator and layout manager.
  - `opcua_client.py`: The asyncua wrapper handling OPC UA protocol logic.
  - `theme.py`: Global styling, CSS rules, and color palettes.
  - `models.py`: Data classes representing servers, nodes, favorites, etc.
  - `widgets/`: Reusable UI components (Server Panel, Favorites Panel, Script Runner, Address Tree, Node Info, etc.).
  - `dialogs/`: Modal dialogs (Settings Dialog).

## 🛟 Troubleshooting

- **Crash on Exit / Error Code 134/130**: If the application crashes unexpectedly when stopping, ensure you disconnect from all servers before closing the app. The `qasync` event loop occasionally raises exceptions if sockets are force-closed.
- **Text Not Visible**: Switch between Light/Dark mode. If a custom OS theme interferes, ensuring the app's default themes are active will override OS colors.
- **Connection Refused**: Ensure the target OPC UA server is actually running and accessible over the network. If using `test_server.py`, ensure it hasn't stopped or crashed.

---
*Built with ❤️ using PyQt6 and FreeOpcUa.*
