# Status Messenger

A simple Python package to manage and display status messages, typically for agentic applications or long-running processes where updates need to be communicated to a UI.

## Installation

```bash
pip install status-messenger
```
*(Once it's published to PyPI)*

Alternatively, to install directly from a Git repository:
```bash
pip install git+https://github.com/your_username/status_messenger.git
```

Or, to install from a local directory (after cloning/downloading):
```bash
cd path/to/status_messenger_py
pip install .
```

## Usage

The package provides functions to add and retrieve status messages.

```python
from status_messenger import add_status_message, get_status_messages, AGENT_STATUS_MESSAGES

# Add a status message
add_status_message("Process started successfully.")
add_status_message("Step 1 completed.")

# Get all current status messages (usually just the latest one)
messages = get_status_messages()
print(messages)  # Output: ['Step 1 completed.']

# You can also access the list directly (though get_status_messages is preferred)
print(AGENT_STATUS_MESSAGES) # Output: ['Step 1 completed.']
```

### Asynchronous Usage with WebSocket and Pub/Sub

The primary design of `status-messenger` is for asynchronous applications.

**Initialization (Async)**

In your main async application (e.g., using FastAPI, Starlette):

```python
import asyncio
from status_messenger import setup_status_messenger_async, add_status_message, stream_status_updates, publish_agent_event, current_websocket_session_id_var

async def main_application_setup():
    loop = asyncio.get_running_loop()
    # This sets up the queue for WebSocket messages and potentially Pub/Sub
    setup_status_messenger_async(loop)
    print("Status Messenger (Async) initialized.")

    # Example: Simulate setting session ID for a task
    token = current_websocket_session_id_var.set("session_123")
    try:
        add_status_message("Async message for session_123.")
        # If Pub/Sub is enabled and configured:
        publish_agent_event({"detail": "User logged in"}, event_type="user_login")
    finally:
        current_websocket_session_id_var.reset(token)

# Typically, you'd run this setup once when your server starts.
# asyncio.run(main_application_setup())
```

**WebSocket Status Updates**

- `add_status_message(message: str)`: Adds a message to an internal queue. It uses `contextvars` to associate the message with the current WebSocket session ID.
- `stream_status_updates() -> AsyncIterator[Tuple[Optional[str], str]]`: An async generator that yields `(session_id, message)` tuples, intended to be consumed by a WebSocket broadcasting mechanism.
- `current_websocket_session_id_var`: A `ContextVar` that should be set with the WebSocket session ID before calling `add_status_message` from within request handlers or tasks associated with a specific session.

**GCP Pub/Sub Event Publishing**

The messenger can also publish structured events to a Google Cloud Pub/Sub topic. This is useful for broader system integration, analytics, or persistent logging of agent activities.

**Enabling Pub/Sub:**

To enable Pub/Sub publishing, the following environment variables must be set:

1.  `STATUS_MESSENGER_PUBSUB_ENABLED="true"`: Explicitly enables the Pub/Sub feature.
2.  `GOOGLE_CLOUD_PROJECT="your-gcp-project-id"`: Your Google Cloud Project ID.
3.  `STATUS_MESSENGER_PUBSUB_TOPIC_ID="your-pubsub-topic-name"`: The ID of the Pub/Sub topic to publish to.

The `google-cloud-pubsub` library must also be installed, and your application environment must be authenticated with GCP (e.g., via Application Default Credentials).

**Publishing Events:**

- `publish_agent_event(event_data: Dict[str, Any], event_type: str = "agent_event")`: Publishes a JSON payload to the configured Pub/Sub topic. The payload includes the `event_data`, `event_type`, a timestamp, and the current `websocket_session_id` (if available).

```python
# Assuming setup_status_messenger_async has been called and Pub/Sub is configured
# and current_websocket_session_id_var is set appropriately.

# Example: Publishing a custom event
event_payload = {
    "tool_used": "calculator",
    "input": "2+2",
    "output": "4"
}
publish_agent_event(event_payload, event_type="tool_interaction")

# This will attempt to send a message like:
# {
#   "websocket_session_id": "session_123",
#   "event_type": "tool_interaction",
#   "timestamp": "2024-06-03T18:00:00.000Z",
#   "data": {
#     "tool_used": "calculator",
#     "input": "2+2",
#     "output": "4"
#   }
# }
# to the specified Pub/Sub topic.
```

### Serving Messages (Example with Flask)

While this package primarily provides the logic for managing status messages, you'll typically need a web server to expose these messages to a frontend. Here's a conceptual example of how you might do this with Flask (Flask is not a direct dependency of this core package).

You would create a separate `server.py` or integrate into your existing Flask application:

```python
# In your Flask app (e.g., app.py or server.py)
from flask import Flask, jsonify
from status_messenger import get_status_messages, add_status_message # Import from your package

app = Flask(__name__)

@app.route('/status', methods=['GET'])
def status_endpoint():
    """Endpoint to get the latest status message."""
    messages = get_status_messages()
    return jsonify(messages)

# Example of how another part of your application might update the status
def some_long_process():
    add_status_message("Starting long process...")
    # ... do work ...
    add_status_message("Long process finished!")

if __name__ == '__main__':
    # To run this example server:
    # 1. Make sure status_messenger is installed (pip install .)
    # 2. Install Flask (pip install Flask)
    # 3. Run this script (python your_server_script_name.py)
    # Then you can access http://localhost:5000/status in your browser or from JS
    app.run(debug=True, port=5000)
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.
