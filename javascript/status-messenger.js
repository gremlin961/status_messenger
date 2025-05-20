/**
 * status_messenger_js - Client-side library to receive and display status messages via WebSocket.
 */

/**
 * Connects to a WebSocket endpoint to receive status updates and displays them
 * in the specified HTML element.
 *
 * @param {string} elementId The ID of the HTML element to display messages in.
 * @param {string} websocketUrl The WebSocket URL to connect to for status messages.
 * @param {number} [reconnectDelayMs=5000] The delay in milliseconds before attempting to reconnect.
 */
function startStatusUpdates(elementId, websocketUrl, reconnectDelayMs = 5000) {
    const displayElement = document.getElementById(elementId);
    let ws = null;

    if (!displayElement) {
        console.error(`[StatusMessenger] Error: Element with ID '${elementId}' not found.`);
        return () => { console.warn("[StatusMessenger] No-op stop function: Element not found."); };
    }

    if (!websocketUrl) {
        console.error("[StatusMessenger] Error: websocketUrl is required.");
        displayElement.textContent = "Error: WebSocket URL not provided.";
        return () => { console.warn("[StatusMessenger] No-op stop function: WebSocket URL not provided."); };
    }

    // Determine WebSocket protocol (ws:// or wss://) if not explicitly provided in websocketUrl
    let finalWebsocketUrl = websocketUrl;
    if (!websocketUrl.startsWith('ws://') && !websocketUrl.startsWith('wss://')) {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        // Assuming websocketUrl might be a path like "/ws/status"
        finalWebsocketUrl = `${wsProtocol}${window.location.host}${websocketUrl.startsWith('/') ? '' : '/'}${websocketUrl}`;
    }
    
    console.log(`[StatusMessenger] Initializing status updates for element '${elementId}' from WebSocket: ${finalWebsocketUrl}`);

    function connect() {
        console.info(`[StatusMessenger] Attempting to connect to WebSocket: ${finalWebsocketUrl}`);
        ws = new WebSocket(finalWebsocketUrl);

        ws.onopen = function () {
            console.info("[StatusMessenger] WebSocket connection opened successfully.");
            displayElement.textContent = "Connected. Waiting for status..."; // Initial message
        };

        ws.onmessage = function (event) {
            try {
                const packet = JSON.parse(event.data);

                if (packet && packet.type === "status" && packet.data !== undefined) {
                    displayElement.innerHTML = ''; // Clear previous content
                    const p = document.createElement('p');
                    p.textContent = packet.data;
                    // Optionally, add a class for styling if needed, e.g., p.classList.add('status-message-item');
                    displayElement.appendChild(p);
                    displayElement.scrollTop = displayElement.scrollHeight; // Scroll to bottom
                } else if (packet) {
                    console.warn("[StatusMessenger] Received WebSocket message of unexpected type or structure:", packet);
                    // Optionally, display a generic message or the raw data if appropriate for debugging
                    // For a dedicated status display, it's often better to ignore non-status messages silently
                    // or provide a subtle indication that non-status data was received.
                    // displayElement.textContent = "Received non-status data (see console)";
                } else {
                    // This case should ideally not be reached if JSON.parse was successful and returned an object.
                    console.warn("[StatusMessenger] Received unparseable or empty packet structure:", event.data);
                }
            } catch (e) {
                console.error("[StatusMessenger] Failed to parse WebSocket message JSON:", event.data, e);
                // Display an error or the raw message if parsing fails
                displayElement.innerHTML = ''; // Clear previous content
                const p = document.createElement('p');
                p.classList.add('error-message'); // Add an error class for styling
                if (typeof event.data === 'string') {
                    p.textContent = `Error parsing message: ${event.data.substring(0,100)}${event.data.length > 100 ? '...' : ''}`;
                } else {
                    p.textContent = "Error processing message. See console.";
                }
                displayElement.appendChild(p);
                displayElement.scrollTop = displayElement.scrollHeight;
            }
        };

        ws.onclose = function (event) {
            console.warn(`[StatusMessenger] WebSocket connection closed. Code: ${event.code}, Reason: '${event.reason}'. Attempting to reconnect in ${reconnectDelayMs}ms.`);
            // Avoid clearing the last known status on temporary disconnects if preferred,
            // but for simplicity, we can set a "reconnecting" message.
            displayElement.innerHTML = ''; // Clear previous content
            const p = document.createElement('p');
            p.textContent = `Connection closed. Reconnecting...`;
            displayElement.appendChild(p);
            displayElement.scrollTop = displayElement.scrollHeight;
            ws = null; // Ensure ws is null so stop function doesn't try to close an already closed socket
            setTimeout(connect, reconnectDelayMs);
        };

        ws.onerror = function (error) {
            console.error("[StatusMessenger] WebSocket error: ", error);
            displayElement.textContent = "WebSocket error. See console for details. Attempting to reconnect...";
            // ws.close() will be called by the browser, leading to onclose handler
        };
    }

    connect(); // Initial connection attempt

    // Return a function to stop WebSocket connection and updates
    return () => {
        if (ws) {
            console.log(`[StatusMessenger] Stopping status updates for element '${elementId}'. Closing WebSocket.`);
            // Prevent reconnection by clearing the onclose handler or using a flag
            ws.onclose = function () { 
                console.log("[StatusMessenger] WebSocket closed by stop function.");
            };
            ws.close();
            ws = null;
        } else {
            console.log(`[StatusMessenger] WebSocket for '${elementId}' already closed or not initialized.`);
        }
    };
}

// Export the function for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { startStatusUpdates };
} else if (typeof window !== 'undefined') {
    window.startStatusUpdates = startStatusUpdates;
}
