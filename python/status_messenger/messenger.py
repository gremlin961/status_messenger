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
import os
import datetime
from contextvars import ContextVar
from typing import List, Dict, Any, Optional, Tuple, AsyncIterator

try:
    from google.cloud import pubsub_v1
    from google.auth.exceptions import DefaultCredentialsError
except ImportError:
    pubsub_v1 = None  # Allows the package to run if google-cloud-pubsub is not installed
    DefaultCredentialsError = None
    print("[StatusMessenger WARNING] google-cloud-pubsub not installed. Pub/Sub features will be unavailable.")


# ContextVar to hold the current WebSocket session ID for the active async context
current_websocket_session_id_var: ContextVar[Optional[str]] = ContextVar("current_websocket_session_id_var", default=None)

# asyncio.Queue to hold (session_id, message) tuples for WebSocket status updates
AGENT_MESSAGE_QUEUE: Optional[asyncio.Queue[Tuple[Optional[str], str]]] = None
_loop: Optional[asyncio.AbstractEventLoop] = None

# GCP Pub/Sub related globals
_pubsub_publisher: Optional[Any] = None # Will be pubsub_v1.PublisherClient if available and configured
_pubsub_topic_path: Optional[str] = None
_pubsub_enabled: bool = False

def _pubsub_callback(future: Any) -> None:
    """Callback for Pub/Sub publish results."""
    try:
        message_id = future.result() # This blocks until the future is resolved
        print(f"[StatusMessenger INFO] Published Pub/Sub message with ID: {message_id}. Future result: {message_id}")
    except Exception as e:
        print(f"[StatusMessenger ERROR] Failed to publish Pub/Sub message: {e}. Exception type: {type(e)}. Future exception: {future.exception()}")

def setup_status_messenger_async(loop: asyncio.AbstractEventLoop) -> None:
    """
    Initializes the status messenger with the asyncio event loop, creates the WebSocket message queue,
    and sets up GCP Pub/Sub publishing if configured via environment variables.
    This should be called once from the main async application at startup.
    """
    global AGENT_MESSAGE_QUEUE, _loop, _pubsub_publisher, _pubsub_topic_path, _pubsub_enabled

    _loop = loop
    AGENT_MESSAGE_QUEUE = asyncio.Queue()
    print("[StatusMessenger] Async WebSocket setup complete, queue created.")

    if pubsub_v1 is None:
        print("[StatusMessenger INFO] GCP Pub/Sub client library not found. Pub/Sub publishing disabled.")
        _pubsub_enabled = False
        return

    pubsub_env_enabled = os.environ.get("STATUS_MESSENGER_PUBSUB_ENABLED", "false").lower() == "true"
    gcp_project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") # Reverted to use .get()
    pubsub_topic_id = os.environ.get("STATUS_MESSENGER_PUBSUB_TOPIC_ID") # Reverted to use .get()

    if pubsub_env_enabled:
        if gcp_project_id and pubsub_topic_id: # Reinstated check for presence
            try:
                _pubsub_publisher = pubsub_v1.PublisherClient()
                _pubsub_topic_path = _pubsub_publisher.topic_path(gcp_project_id, pubsub_topic_id)
                _pubsub_enabled = True
                print(f"[StatusMessenger] GCP Pub/Sub publishing enabled for topic: {_pubsub_topic_path}")
            except DefaultCredentialsError:
                print("[StatusMessenger ERROR] GCP Default Credentials not found. Pub/Sub publishing disabled. Ensure ADC is configured.")
                _pubsub_enabled = False
            except Exception as e:
                print(f"[StatusMessenger ERROR] Failed to initialize GCP Pub/Sub publisher: {e}. Pub/Sub publishing disabled.")
                _pubsub_enabled = False
        else:
            print("[StatusMessenger WARNING] Pub/Sub enabled but GOOGLE_CLOUD_PROJECT or STATUS_MESSENGER_PUBSUB_TOPIC_ID not set in environment. Pub/Sub publishing disabled.")
            _pubsub_enabled = False
    else:
        print("[StatusMessenger INFO] GCP Pub/Sub publishing not enabled via STATUS_MESSENGER_PUBSUB_ENABLED environment variable.")
        _pubsub_enabled = False


def add_status_message(message: str) -> None:
    """
    Adds a status message to the queue, associating it with the WebSocket session ID
    from the current asyncio context. Prints to console.
    Adds a status message to the WebSocket queue, associating it with the WebSocket session ID
    from the current asyncio context. Prints to console.
    """
    if AGENT_MESSAGE_QUEUE is None or _loop is None:
        print("[StatusMessenger ERROR] WebSocket Messenger not initialized. Call setup_status_messenger_async first.")
        print(f"Orphaned WebSocket status message (messenger not ready): {message}")
        return

    websocket_session_id = current_websocket_session_id_var.get()

    if websocket_session_id is None:
        print(f"[StatusMessenger WARNING] No WebSocket session ID in context for WebSocket message: {message}. Message will be queued without a specific session target.")
    
    print(f"WebSocket Status for session {websocket_session_id or 'UnknownSession'}: {message}")

    try:
        _loop.call_soon_threadsafe(AGENT_MESSAGE_QUEUE.put_nowait, (websocket_session_id, message))
    except RuntimeError:
        try:
            AGENT_MESSAGE_QUEUE.put_nowait((websocket_session_id, message))
        except Exception as e:
            print(f"[StatusMessenger ERROR] Failed to queue WebSocket message directly: {e}")


def publish_agent_event(event_data: Dict[str, Any], event_type: str = "agent_event") -> None:
    """
    Publishes a structured event to the configured GCP Pub/Sub topic.
    The event_data dictionary will be serialized to JSON.
    """
    global _pubsub_enabled, _pubsub_publisher, _pubsub_topic_path, _loop

    if not _pubsub_enabled or _pubsub_publisher is None or _pubsub_topic_path is None or _loop is None:
        print(f"[StatusMessenger WARNING] Pub/Sub publishing is not enabled or not configured. Event (type: {event_type}) not published.")
        if not _pubsub_enabled:
             print("[StatusMessenger DETAIL] Reason: STATUS_MESSENGER_PUBSUB_ENABLED is false or required env vars missing.")
        elif _pubsub_publisher is None:
             print("[StatusMessenger DETAIL] Reason: Pub/Sub publisher client not initialized.")
        # Ensure _loop is checked as well if it's critical for this path
        elif _loop is None:
             print("[StatusMessenger DETAIL] Reason: Asyncio event loop not available.")
        return

    websocket_session_id = current_websocket_session_id_var.get()
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"

    payload = {
        "websocket_session_id": websocket_session_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "data": event_data,
    }

    try:
        data_bytes = json.dumps(payload).encode("utf-8")

        # Define the function that will perform the publish and add the callback
        def do_publish():
            try:
                # This is the actual publish call that returns a Future
                publish_future = _pubsub_publisher.publish(_pubsub_topic_path, data_bytes)
                # Add the callback to the Future returned by the publish method
                publish_future.add_done_callback(_pubsub_callback)
                # The message below might be slightly premature, as the callback confirms actual publishing.
                # Consider moving detailed success log to the callback.
                print(f"[StatusMessenger INFO] Submitted event (type: {event_type}) for Pub/Sub publishing. Awaiting callback for result.")
            except Exception as e:
                # This catch is for errors during the _pubsub_publisher.publish() call itself,
                # or add_done_callback, if it's not running on the loop yet.
                print(f"[StatusMessenger ERROR] Error when trying to initiate Pub/Sub publish (type: {event_type}): {e}")


        # Schedule do_publish to run on the event loop
        # This is thread-safe and ensures the publish call and callback setup
        # happen within the context of the asyncio loop.
        _loop.call_soon_threadsafe(do_publish)

    except Exception as e:
        # This catch is for errors like JSON serialization before even attempting to publish.
        print(f"[StatusMessenger ERROR] Failed to prepare event for Pub/Sub publishing (type: {event_type}): {e}")


async def stream_status_updates() -> AsyncIterator[Tuple[Optional[str], str]]:
    """
    Asynchronously yields (websocket_session_id, message) tuples from the WebSocket message queue.
    """
    if AGENT_MESSAGE_QUEUE is None:
        print("[StatusMessenger ERROR] WebSocket Messenger not initialized for streaming. Call setup_status_messenger_async first.")
        return

    while True:
        session_id, message = await AGENT_MESSAGE_QUEUE.get()
        yield session_id, message
        AGENT_MESSAGE_QUEUE.task_done()
