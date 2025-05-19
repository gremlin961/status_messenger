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
