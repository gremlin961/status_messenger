# Copyright 2024 Google, LLC. This software is provided as-is,
# without warranty or representation for any use or purpose. Your
# use of it is subject to your agreement with Google.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import asyncio
from contextvars import ContextVar # Added import
from typing import List, Dict, Any, Optional, Tuple, AsyncIterator

# ContextVar to hold the current WebSocket session ID for the active async context
current_websocket_session_id_var: ContextVar[Optional[str]] = ContextVar("current_websocket_session_id_var", default=None)

# asyncio.Queue to hold (session_id, message) tuples
AGENT_MESSAGE_QUEUE: Optional[asyncio.Queue[Tuple[Optional[str], str]]] = None # session_id can be Optional
_loop: Optional[asyncio.AbstractEventLoop] = None

def setup_status_messenger_async(loop: asyncio.AbstractEventLoop) -> None:
    """
    Initializes the status messenger with the asyncio event loop and creates the queue.
    This should be called once from the main async application at startup.
    """
    global AGENT_MESSAGE_QUEUE, _loop
    _loop = loop
    AGENT_MESSAGE_QUEUE = asyncio.Queue() # Queue stores (Optional[str], str)
    print("[StatusMessenger] Async setup complete, queue created.")

def add_status_message(message: str) -> None: # session_id parameter removed
    """
    Adds a status message to the queue, associating it with the WebSocket session ID
    from the current asyncio context. Prints to console.
    """
    if AGENT_MESSAGE_QUEUE is None or _loop is None:
        print("[StatusMessenger ERROR] Messenger not initialized. Call setup_status_messenger_async first.")
        print(f"Orphaned status message (messenger not ready): {message}")
        return

    # Get the WebSocket session ID from the context variable
    websocket_session_id = current_websocket_session_id_var.get()

    if websocket_session_id is None:
        print(f"[StatusMessenger WARNING] No WebSocket session ID in context for message: {message}. Message will be queued without a specific session target.")
        # Decide handling: queue with None, or a placeholder, or discard.
        # Queuing with None allows broadcaster to decide (e.g., log, or if single-user mode, send anyway).
    
    print(f"Status for session {websocket_session_id or 'UnknownSession'}: {message}")  # Log to console

    try:
        # If called from a thread different from the loop's thread (e.g. sync agent tool).
        _loop.call_soon_threadsafe(AGENT_MESSAGE_QUEUE.put_nowait, (websocket_session_id, message))
    except RuntimeError:
        # Fallback if loop is already running in the current thread (e.g. called from async code directly)
        try:
            AGENT_MESSAGE_QUEUE.put_nowait((websocket_session_id, message))
        except Exception as e:
            print(f"[StatusMessenger ERROR] Failed to queue message directly: {e}")


async def stream_status_updates() -> AsyncIterator[Tuple[Optional[str], str]]: # session_id can be Optional
    """
    Asynchronously yields (websocket_session_id, message) tuples from the queue.
    """
    if AGENT_MESSAGE_QUEUE is None:
        print("[StatusMessenger ERROR] Messenger not initialized for streaming. Call setup_status_messenger_async first.")
        # To make this an empty async generator in this case, simply return.
        # The `async def` with a `yield` elsewhere already makes it an async generator.
        # An `async def` function without any `yield` is a coroutine function,
        # but if it has at least one `yield`, it's an async generator.
        # If this path is taken, the generator will simply finish immediately.
        return

    while True:
        session_id, message = await AGENT_MESSAGE_QUEUE.get()
        yield session_id, message
        AGENT_MESSAGE_QUEUE.task_done()

# Example for serving messages with Flask (optional, can be in a separate server file)
# from flask import Flask, jsonify

# def create_flask_app():
#     app = Flask(__name__)

#     @app.route('/status', methods=['GET'])
#     def status():
#         return jsonify(get_status_messages())

#     return app

# if __name__ == '__main__':
#     # This is for testing the Flask app directly
#     # In a real package, you'd import and run this from a different script
#     # or use a production server like Gunicorn.
#     # For the package, we'll focus on providing the functions.
#     # The Flask app part would be an example of how to use it.
#     # app = create_flask_app()
#     # app.run(debug=True, port=5001) # Example port
#     pass
