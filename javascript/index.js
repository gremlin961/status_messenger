/**
 * status_messenger_js - Client-side library to fetch and display status messages.
 */

/**
 * Starts polling for status updates from a given endpoint and displays them
 * in the specified HTML element.
 *
 * @param {string} elementId The ID of the HTML element to display messages in.
 * @param {string} statusEndpointUrl The URL to fetch status messages from.
 * @param {number} [intervalMs=2000] The polling interval in milliseconds. Defaults to 2000ms.
 */
function startStatusUpdates(elementId, statusEndpointUrl, intervalMs = 2000) {
    const displayElement = document.getElementById(elementId);

    if (!displayElement) {
        console.error(`[StatusMessenger] Error: Element with ID '${elementId}' not found.`);
        return;
    }

    if (!statusEndpointUrl) {
        console.error("[StatusMessenger] Error: statusEndpointUrl is required.");
        displayElement.textContent = "Error: Status endpoint URL not provided.";
        return;
    }

    console.log(`[StatusMessenger] Initializing status updates for element '${elementId}' from '${statusEndpointUrl}' every ${intervalMs}ms.`);

    const fetchAndUpdateStatus = async () => {
        try {
            const response = await fetch(statusEndpointUrl);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const messages = await response.json(); // Expects server to return JSON array of strings

            if (Array.isArray(messages) && messages.length > 0) {
                // Display the latest message, or join them if multiple are relevant
                displayElement.textContent = messages.join("\n");
            } else if (Array.isArray(messages) && messages.length === 0) {
                // displayElement.textContent = "No status messages."; // Or keep the old one
            } else {
                // displayElement.textContent = "Waiting for status...";
            }
        } catch (error) {
            console.error("[StatusMessenger] Error fetching status:", error);
            // displayElement.textContent = "Error fetching status. See console for details.";
            // Optionally, stop polling on certain errors or implement backoff
        }
    };

    // Initial fetch
    fetchAndUpdateStatus();

    // Start polling
    const intervalId = setInterval(fetchAndUpdateStatus, intervalMs);

    // Return a function to stop polling if needed
    return () => {
        console.log(`[StatusMessenger] Stopping status updates for element '${elementId}'.`);
        clearInterval(intervalId);
    };
}

// Export the function for use in other scripts if this becomes a module
// For a simple script included via <script> tag, this isn't strictly necessary
// but good practice for potential bundling/module usage.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { startStatusUpdates };
} else if (typeof window !== 'undefined') {
    window.startStatusUpdates = startStatusUpdates;
}
