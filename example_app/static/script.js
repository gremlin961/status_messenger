// DOM Elements
const messageForm = document.getElementById("messageForm");
const messageInputElement = document.getElementById("messageInput"); // Renamed variable
const messagesDiv = document.getElementById("messages");
const sendButton = document.getElementById("sendButton");
// const agentStatusMessagesDiv = document.getElementById("agent-status-messages"); // Will be handled by status-messenger library

let currentMessageId = null;
let currentMessageBuffer = ""; // Buffer for current agent message text for Markdown rendering
let ws = null; // WebSocket instance, initialized later

// Generate a unique session ID for this client session
const sessionId = Math.random().toString(36).substring(2, 10) + Date.now().toString(36).slice(-4);
console.log("Client Session ID:", sessionId);

// Determine WebSocket protocol (ws:// or wss://)
const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
const ws_url = `${wsProtocol}${window.location.host}/ws/${sessionId}`;

function connectWebSocket() {
    console.info(`Attempting to connect to WebSocket: ${ws_url}`);
    ws = new WebSocket(ws_url);
    addWebSocketHandlers(ws);
}

// function displayStatusMessage(text, type = 'status') { // This function will be removed
//     const p = document.createElement('p');
//     p.classList.add('status-message');
//     if (type === 'error') {
//         p.classList.add('error-message');
//     }
//     p.textContent = text;
//     messagesDiv.appendChild(p); // This was writing to messagesDiv, not agentStatusMessagesDiv
//     messagesDiv.scrollTop = messagesDiv.scrollHeight;
// }

function displayUserMessage(text) {
    const p = document.createElement("p");
    p.classList.add('user-message-display');
    p.innerHTML = `<strong>You:</strong> `; // Use innerHTML for the strong tag
    const textNode = document.createTextNode(text); // Sanitize user input by creating a text node
    p.appendChild(textNode);
    messagesDiv.appendChild(p);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// WebSocket Event Handlers
function addWebSocketHandlers(websocketInstance) {
  websocketInstance.onopen = function () {
    console.info("WebSocket connection opened successfully (client-side).");
    sendButton.disabled = false;
    // Initial connection status will be handled by status-messenger.js via its own WebSocket connection or messages
    // The form submit handler is now added outside onopen, once.
  };

  websocketInstance.onmessage = function (event) {
    let packet;
    try {
        packet = JSON.parse(event.data);
    } catch (e) {
        console.error("Failed to parse WebSocket message JSON:", event.data, e);
        // Error display for main messagesDiv if needed, or rely on status-messenger for its own errors
        const p = document.createElement('p');
        p.classList.add('error-message');
        p.textContent = "Received unparsable message from server.";
        messagesDiv.appendChild(p);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        return;
    }

    // --- Handle server-side log messages ---
    if (packet.type === "server_log") {
        let consoleMethod = console.log; // Default
        const level = packet.level ? packet.level.toUpperCase() : 'LOG';
        switch (level) {
            case "INFO":    consoleMethod = console.info; break;
            case "WARN":    consoleMethod = console.warn; break;
            case "ERROR":   consoleMethod = console.error; break;
            case "DEBUG":   consoleMethod = console.debug; break;
            default:        consoleMethod = console.log;
        }
        // The message from server now includes session_id, so no need to add it here.
        consoleMethod(`[SERVER ${level}]: ${packet.message}`);
        return; // This was a log message, don't process as agent message
    }
    // --- End server-side log message handling ---

    // --- Application status messages (packet.type === "status") are now handled by status-messenger.js ---
    // The main WebSocket connection (ws) will ignore them if they are still sent on this channel.
    // Ideally, the server would send them on a dedicated status WebSocket if a separate one was used,
    // or status-messenger.js connects to the same endpoint and filters.
    // Given status-messenger.js will connect to ws_url, it will receive these.

    // --- Regular agent message processing ---
    if (packet.type === "status") { // Explicitly ignore status messages on this handler
        console.debug("[Main WS] Ignoring status packet, should be handled by status-messenger.js", packet);
        return;
    }
    
    if (packet.turn_complete) { // Simplified check
      console.info("Agent turn complete (client received).");
      currentMessageId = null;
      currentMessageBuffer = ""; // Reset buffer
      return;
    }

    if (packet.interrupted) {
        console.warn("Agent turn interrupted (client received).");
        if(currentMessageId) {
            const messageElement = document.getElementById(currentMessageId);
            if (messageElement) {
                const interruptedSpan = document.createElement('span');
                interruptedSpan.classList.add('interrupted-text');
                interruptedSpan.textContent = ' (Interrupted)';
                messageElement.appendChild(interruptedSpan);
            }
        }
        currentMessageId = null;
        currentMessageBuffer = ""; // Reset buffer
        return;
    }

    if (packet.message !== undefined && packet.message !== null) { // Check if message exists
        let messageElement;
        if (currentMessageId === null) { // Start of a new agent message stream
            currentMessageId = "agent-msg-" + Math.random().toString(36).substring(2, 9);
            messageElement = document.createElement("p");
            messageElement.id = currentMessageId;
            messageElement.classList.add('agent-message-display');
            messagesDiv.appendChild(messageElement);
            currentMessageBuffer = packet.message; // Start buffer with first chunk
        } else { // Continuation of an agent message stream
            messageElement = document.getElementById(currentMessageId);
            if (messageElement) {
                currentMessageBuffer = packet.message; // Set buffer to the current packet's message
            } else {
                console.error("Orphaned agent message chunk. No element for ID:", currentMessageId);
                currentMessageId = null; 
                currentMessageBuffer = "";
                return;
            }
        }

        if (messageElement && typeof marked !== 'undefined') {
            try {
                messageElement.innerHTML = marked.parse(currentMessageBuffer);
            } catch (error) {
               console.error("Error parsing Markdown:", error, "Buffer:", currentMessageBuffer);
               messageElement.textContent = currentMessageBuffer; // Fallback to plain text
            }
        } else if (messageElement) {
            console.warn("Marked library not loaded. Displaying as plain text.");
            messageElement.textContent = currentMessageBuffer;
        }
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
  };

   websocketInstance.onclose = function (event) {
    console.warn(`WebSocket connection closed (client-side). Code: ${event.code}, Reason: '${event.reason}'`);
    sendButton.disabled = true;
    // Connection closed status for the main chat WebSocket will be handled by status-messenger.js for its display
    // This WebSocket will attempt to reconnect for chat functionality.

    currentMessageId = null;
    currentMessageBuffer = "";

    setTimeout(function () {
      console.info("Attempting to reconnect WebSocket for chat...");
      connectWebSocket(); 
    }, 5000);
  };

  websocketInstance.onerror = function (error) {
    console.error("WebSocket error (client-side): ", error);
    // WebSocket error display for the main chat WebSocket will be handled by status-messenger.js for its display
  };
}

if (messageForm) {
    messageForm.onsubmit = function (e) {
        e.preventDefault();
        const messageText = messageInputElement.value.trim();
        if (!messageText) return false;
        if (ws && ws.readyState === WebSocket.OPEN) {
            displayUserMessage(messageText);
            ws.send(messageText);
            messageInputElement.value = ""; 
        } else {
            // Error if cannot send message - this could be displayed in the main messagesDiv or rely on status-messenger
            console.error("Cannot send message. Main WebSocket connection not active.");
            // Optionally, display a message in messagesDiv or a general error area if not using status-messenger for this
            const p = document.createElement('p');
            p.classList.add('error-message');
            p.textContent = "Cannot send message. Connection not active.";
            messagesDiv.appendChild(p);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        return false; 
    };
} else {
    console.error("Message form not found in the DOM.");
}

connectWebSocket(); // Connect the main chat WebSocket

// Initialize status updates using the status-messenger library
// It will connect to the same WebSocket endpoint and filter for status messages.
if (typeof window.startStatusUpdates === 'function') {
    console.info("Initializing status-messenger for #status-container");
    // The ws_url is the same as the main chat, as the server sends all message types over it.
    // status-messenger.js is now responsible for filtering and displaying only 'status' type messages.
    window.startStatusUpdates('status-container', ws_url);
} else {
    console.error("status-messenger.js (startStatusUpdates) not found. Status messages will not be displayed by the library.");
}


function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) return '';
    return unsafe
         .toString()
         .replace(/&/g, "&")
         .replace(/</g, "<")
         .replace(/>/g, ">")
         .replace(/"/g, "\"")
         .replace(/'/g, "&#039;");
}
