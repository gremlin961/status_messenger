# status_messenger

This repository contains the source code for the `status_messenger` module, available for both Python and JavaScript.

`status_messenger` is designed to facilitate sending notifications and messages to a user, particularly within a multi-agent workflow utilizing Google's Agent Development Kit (ADK).

## Overview

The primary goal of this project is to demonstrate how `status_messenger` can be integrated into applications to provide clear and timely status updates to users.

## Integrating Status Messenger

This guide outlines how to integrate the `status_messenger` system into your application, enabling agents to send real-time status updates to a specific user's UI. This system is designed with a Python backend (typically for a server like FastAPI) and a JavaScript client-side component.

### Core Concepts

*   **Python Package (`status_messenger`):** Provides server-side utilities to queue and manage status messages. It uses `contextvars` to associate messages with the correct WebSocket session.
*   **JavaScript Library (`status-messenger.js`):** A client-side library that establishes a WebSocket connection (or uses an existing one if modified) to receive status messages and display them in a designated HTML element. It shows only the latest message received.
*   **WebSocket Communication:** Status messages are sent from the server to the relevant client over a WebSocket connection.
*   **Session-Specific Updates:** The system ensures that status messages from an agent interaction are routed only to the specific user/session involved.
*   **GCP Pub/Sub Event Publishing (Python):** The Python package can also publish structured events to a Google Cloud Pub/Sub topic, allowing for broader system integration, analytics, or persistent logging of agent activities. This is an optional feature configured via environment variables.

### Server-Side Integration (Python - Example with FastAPI)

**1. Install the Python Package:**
   Follow the installation instructions in `python/README.md`. Typically, this involves installing the package into your Python environment:
   ```bash
   # From the root of this repository
   cd python
   pip install -e . 
   ```
   Ensure your virtual environment is activated.

**2. Initialize Status Messenger in Your Main Application (e.g., `main.py` for FastAPI):**
   At application startup, you need to initialize the `status_messenger` with the current asyncio event loop and start a background task to broadcast messages.

   ```python
   # In your main application file (e.g., main.py)
   import asyncio
   import status_messenger # From your installed package
   # Ensure you have 'active_websockets: Dict[str, WebSocket]' defined globally or accessible
   # And a function like 'broadcast_app_status_to_client(websocket, message_text, session_id)'

   @app.on_event("startup") # Assuming FastAPI app instance 'app'
   async def startup_event():
       loop = asyncio.get_running_loop()
       status_messenger.setup_status_messenger_async(loop)
       asyncio.create_task(status_message_broadcaster(), name="status_message_broadcaster_task")
       logger.info("Status message broadcaster task scheduled for startup.")
   ```

**3. Implement the Status Message Broadcaster (`main.py`):**
   This asynchronous task consumes messages from the status messenger's queue and sends them to the correct client's WebSocket connection.

   ```python
   # In your main application file (e.g., main.py)
   # Needs:
   # import json
   # from starlette.websockets import WebSocketState # If using for checks
   # logger = logging.getLogger(__name__) # For logging
   # active_websockets: Dict[str, WebSocket] = {} # Your global store of active connections

   async def broadcast_app_status_to_client(websocket: WebSocket, status_text: str, session_id: str):
       """Helper to send a formatted status message to a single WebSocket client."""
       if websocket.client_state == WebSocketState.CONNECTED: # Or your check for connected state
           payload = {"type": "status", "data": status_text}
           await websocket.send_text(json.dumps(payload))
           logger.info(f"[{session_id}] SENT_STATUS_TO_CLIENT: {status_text}")

   async def status_message_broadcaster():
       logger.info("Status message broadcaster task starting.")
       # stream_status_updates yields (websocket_session_id, message_text)
       async for websocket_session_id, message_text in status_messenger.stream_status_updates():
           if websocket_session_id is None:
               logger.warn(f"Status message received with no session ID: {message_text}. Not broadcasting.")
               continue

           logger.debug(f"Received status for session {websocket_session_id} from queue: {message_text}")
           ws = active_websockets.get(websocket_session_id)
           
           if ws:
               try:
                   await broadcast_app_status_to_client(ws, message_text, websocket_session_id)
               except Exception as e:
                   logger.error(f"[{websocket_session_id}] Error sending status to client via broadcaster: {e}", exc_info=True)
           else:
               logger.warn(f"[{websocket_session_id}] No active WebSocket found for status message: {message_text}")
   ```

**4. Set WebSocket Session ID in Context (`main.py`):**
   When a client establishes a WebSocket connection, its unique session ID (typically from the URL) must be set into the context variable provided by `status_messenger`. This allows `add_status_message` to automatically pick it up.

   ```python
   # In your main application file (e.g., main.py, inside your WebSocket endpoint)
   # Import the ContextVar from the status_messenger package
   from status_messenger.messenger import current_websocket_session_id_var 

   @app.websocket("/ws/{client_ws_session_id}") # client_ws_session_id from URL path
   async def websocket_endpoint(websocket: WebSocket, client_ws_session_id: str):
       await websocket.accept()
       active_websockets[client_ws_session_id] = websocket # Store the WebSocket
       
       context_var_token = None # For resetting the context variable
       try:
           # Set the WebSocket session ID for the current asynchronous context
           context_var_token = current_websocket_session_id_var.set(client_ws_session_id)
           
           # --- Your agent execution logic for this session happens here ---
           # This is where your ADK Runner would execute, and agents would call tools.
           # Example:
           # await handle_agent_interaction(websocket, client_ws_session_id) 
           # --- End of agent execution logic ---

           # Keep connection open if agent interaction is done but WebSocket should persist
           while True: # Or your application's specific logic for WebSocket lifetime
               await websocket.receive_text() # Example: keep alive by waiting for messages

       except WebSocketDisconnect:
           logger.info(f"[{client_ws_session_id}] Client disconnected.")
       except Exception as e:
           logger.error(f"[{client_ws_session_id}] Error in WebSocket endpoint: {e}", exc_info=True)
       finally:
           if context_var_token:
               current_websocket_session_id_var.reset(context_var_token)
           active_websockets.pop(client_ws_session_id, None)
           logger.info(f"[{client_ws_session_id}] Cleaned up WebSocket session.")
   ```

**5. Agent Tool Usage (e.g., in your `agent.py`):**
   Agents use a simple tool that calls `add_status_message` with only the message string. The WebSocket session ID is picked up automatically from the context variable set in `main.py`.

   ```python
   # In your agent's tool definition file (e.g., agent.py or a tools.py)
   from status_messenger import add_status_message # From your installed package

   def status_message_tool(message: str) -> str:
       """Sends a status update message related to the agent's current task."""
       add_status_message(message) # session_id is handled by contextvar via current_websocket_session_id_var
       return f"Status message '{message}' acknowledged." 
   
   # This 'status_message_tool' is then registered with your ADK Agent.
   # The LLM should be prompted to call this tool with just the message string argument.
   ```

**6. Publishing Events to GCP Pub/Sub (Python - Optional):**
   If configured, the Python `status_messenger` can also publish events.

   ```python
   # In your agent's tool or other server-side logic
   from status_messenger import publish_agent_event # Import the function

   # Assuming setup_status_messenger_async has been called,
   # Pub/Sub is enabled via environment variables (see python/README.md for details),
   # and current_websocket_session_id_var is set if you want the session ID in the event.

   event_details = {"action": "item_purchased", "item_id": "XYZ123", "user_id": "user_abc"}
   publish_agent_event(event_details, event_type="ecommerce_transaction")
   # This will send a structured JSON payload to the configured Pub/Sub topic.
   ```
   For details on enabling and configuring Pub/Sub, refer to `python/README.md`. Key environment variables include `STATUS_MESSENGER_PUBSUB_ENABLED`, `GOOGLE_CLOUD_PROJECT`, and `STATUS_MESSENGER_PUBSUB_TOPIC_ID`.

### Client-Side Integration (JavaScript)

**1. Include `status-messenger.js`:**
   Ensure the `status-messenger.js` library (from the `javascript/` directory of this project) is included in your HTML page.
   ```html
   <script src="/path/to/status-messenger.js" defer></script> 
   ```
   (In the example app, it's copied to `static/status-messenger.js` and loaded from there.)

**2. Prepare an HTML Element:**
   Add a `div` (or another element) to your HTML where status messages will be displayed.
   ```html
   <div id="my-status-display-area"></div>
   ```

**3. Initialize Status Updates in Your Client-Side JavaScript:**
   In your main JavaScript file, after establishing your primary WebSocket connection (if any), initialize the status message display.

   ```javascript
   // In your main client-side script (e.g., script.js)

   const websocketBaseUrl = (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host;
   const clientSessionId = generateUniqueId(); // Your function to create a unique ID for the session
   const mainWebSocketUrl = `${websocketBaseUrl}/ws/${clientSessionId}`;

   // Example: Connect your main application WebSocket
   // const mainSocket = new WebSocket(mainWebSocketUrl);
   // ... setup mainSocket handlers ...

   // Initialize status message display
   const agentStatusElementId = "my-status-display-area"; // ID of your display div
   
   if (typeof window.startStatusUpdates === 'function') {
       console.info(`Initializing status updates for element '#${agentStatusElementId}'`);
       // status-messenger.js will establish its own WebSocket connection to this URL.
       // The server (main.py) uses the session ID from the URL to route messages.
       // The client-side status-messenger.js filters for messages of type: "status".
       window.startStatusUpdates(agentStatusElementId, mainWebSocketUrl); 
   } else {
       console.error("status-messenger.js (startStatusUpdates function) not found.");
   }
   ```
   **Note:** The `status-messenger.js` library, as provided in this project, creates its own WebSocket connection. The `example_app/main.py` server is set up to handle this: the `active_websockets` dictionary will store the WebSocket object associated with the `clientSessionId` from the URL. If both your main application logic and `status-messenger.js` connect using the exact same URL (including the same session ID path parameter), the last one to connect will be the one stored in `active_websockets` for that ID. Status messages are then sent to this specific WebSocket.

**4. Expected WebSocket Message Format (Server to Client):**
   The client-side `status-messenger.js` expects status messages in this JSON format:
   ```json
   {
       "type": "status",
       "data": "Your status message here..."
   }
   ```
   The `broadcast_app_status_to_client` helper function (shown in the server-side setup) already sends messages in this format.

This detailed guide should help developers integrate the `status_messenger` into their projects.

## Examples

Example implementations showcasing the usage of `status_messenger` can be found in the `example_app/` directory:

*   **`example_app/main.py`**: A Python FastAPI application demonstrating server-side integration. It sends various message types, including status updates, over a WebSocket connection.
*   **`example_app/static/` directory**: Contains the client-side example:
    *   `index.html`: The main HTML page for the example application.
    *   `script.js`: Handles the primary chat functionality and user interactions. It now integrates the `status_messenger` JavaScript library (loaded via CDN) to display status messages received from the server in a dedicated area.

## Running the Example Application

The `example_app/` can be easily run using the provided shell script. This script handles the necessary setup for the Google Cloud Project ID and launches the Uvicorn server.

1.  **Navigate to the example app directory:**
    ```bash
    cd example_app
    ```

2.  **Make the script executable (if you haven't already):**
    ```bash
    chmod +x run_app.sh
    ```

3.  **Run the script:**
    ```bash
    ./run_app.sh
    ```
    The script will guide you if the `.env` file for the agent needs to be configured with your Google Cloud Project ID.
    Once running, the application will be accessible at `http://localhost:8000`.

## Modules

### Python

The Python module can be found in the `python/` directory. It includes the `status_messenger` library and setup instructions.

### JavaScript

The JavaScript package is located in the `javascript/` directory. It provides the necessary files and instructions for integrating `status_messenger` into JavaScript-based projects.

## Getting Started

Please refer to the README files within the `python/` and `javascript/` directories for specific installation and usage instructions for each module.
