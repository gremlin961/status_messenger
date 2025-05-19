# Status Messenger JS Client

A simple JavaScript client to fetch and display status messages from a server endpoint. This is intended to work with a backend that provides status updates, such as the `status-messenger` Python package.

## Installation

```bash
npm install status-messenger
```
*(Once it's published to npm)*

Alternatively, you can include the `index.js` file directly in your HTML or bundle it with your existing JavaScript assets.

If installing from a local path (e.g., during development or if not publishing to npm):
```bash
npm install /path/to/status_messenger_js 
```
Or add it as a local dependency in your project's `package.json`:
```json
"dependencies": {
  "status-messenger": "file:../path/to/status_messenger_js"
}
```

## Usage

### 1. Include the script

If using as a module (e.g., with a bundler like Webpack or Rollup):
```javascript
// In your application's JavaScript
import { startStatusUpdates } from 'status-messenger';
// or const { startStatusUpdates } = require('status-messenger');

// Call the function when your page is ready
document.addEventListener('DOMContentLoaded', () => {
    const stopUpdates = startStatusUpdates(
        'status-display-element-id', // ID of the HTML element to update
        '/api/status'                // URL of your status endpoint
        // 2000                      // Optional: polling interval in ms (default: 2000)
    );

    // To stop polling later, e.g., when navigating away or component unmounts:
    // stopUpdates();
});
```

If including directly in an HTML file:
```html
<!DOCTYPE html>
<html>
<head>
    <title>Status Page</title>
</head>
<body>
    <h1>Current Status:</h1>
    <div id="status-message-area">Waiting for status...</div>

    <!-- Include the script -->
    <script src="path/to/status_messenger_js/index.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            // Ensure startStatusUpdates is available on the window object
            if (window.startStatusUpdates) {
                const stopPolling = window.startStatusUpdates(
                    'status-message-area',      // ID of the div above
                    '/api/status',              // Your backend status endpoint
                    3000                        // Optional: Poll every 3 seconds
                );

                // Example: Stop polling after 30 seconds for this demo
                // setTimeout(stopPolling, 30000);
            } else {
                console.error('startStatusUpdates function not found. Check script path.');
                document.getElementById('status-message-area').textContent = 'Error: Status script not loaded.';
            }
        });
    </script>
</body>
</html>
```

### 2. Prepare your HTML

Ensure you have an HTML element with the ID you provide to `startStatusUpdates`.
```html
<div id="status-display-element-id"></div>
```

### 3. Backend Endpoint

This client expects the `statusEndpointUrl` to return a JSON array of strings. For example:
```json
["Processing item 5 of 10...", "Almost there!"]
```
The client will display these messages, typically joined by newlines if multiple are provided. The `status_messenger` Python package's `AGENT_STATUS_MESSAGES` list, when served via a Flask/FastAPI endpoint, should provide data in this format.

## API

### `startStatusUpdates(elementId, statusEndpointUrl, [intervalMs])`

-   `elementId` (string, required): The ID of the HTML element where status messages will be displayed.
-   `statusEndpointUrl` (string, required): The URL from which to fetch status messages.
-   `intervalMs` (number, optional): The polling interval in milliseconds. Defaults to `2000` (2 seconds).

Returns a function that can be called to stop the polling.

## Development

This is a simple package with no build step. To make changes, edit `index.js` directly.

If you wish to add a build process (e.g., for minification, transpilation, or bundling into different module formats), you would typically add development dependencies like Webpack, Rollup, Babel, or Terser, and configure scripts in `package.json`.
