import os
import json
import asyncio
import logging

from pathlib import Path
from dotenv import load_dotenv
from typing import Dict # For type hinting active_websockets

from google.genai.types import (
    Part,
    Content,
)

from google.adk.runners import Runner
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect
from starlette.websockets import WebSocketState
# --- Agent Imports for the Google ADK ---
from example_agent.agent import root_agent # Using the agent from example_agent
# --- Status Messenger Import ---
import status_messenger # Import the module
from status_messenger.messenger import current_websocket_session_id_var # Import the ContextVar from messenger
# For application-level status updates


# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


APP_NAME = "ADK Chat App" # Updated App Name
session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()

# Global store for active websockets, mapping session_id to WebSocket object
active_websockets: Dict[str, WebSocket] = {}

async def broadcast_app_status_to_client(websocket: WebSocket, status_text: str, session_id: str):
    """Sends an application status message (type: 'status') to a single WebSocket client."""
    # try...except removed
    if websocket.client_state == WebSocketState.CONNECTED:
        payload = {"type": "status", "data": status_text} # As expected by index.html
        await websocket.send_text(json.dumps(payload))
        logger.info(f"[{session_id}] SENT_APP_STATUS_TO_CLIENT: {status_text}")

async def status_message_broadcaster():
    """
    Consumes status messages from status_messenger's queue and sends them
    to the appropriate WebSocket client based on session_id.
    """
    logger.info("Status message broadcaster task starting.")
    async for target_session_id, message_text in status_messenger.stream_status_updates():
        logger.debug(f"Received status for session {target_session_id} from queue: {message_text}")
        ws = active_websockets.get(target_session_id)
        if ws and ws.client_state == WebSocketState.CONNECTED:
            try:
                # broadcast_app_status_to_client already logs success/failure
                await broadcast_app_status_to_client(ws, message_text, target_session_id)
            except Exception as e:
                # This catch is if broadcast_app_status_to_client itself raises an unhandled error
                # (though we removed its internal try-except, so errors would propagate here)
                logger.error(f"[{target_session_id}] Error in status_message_broadcaster while sending: {e}", exc_info=True)
        elif ws and ws.client_state != WebSocketState.CONNECTED:
            logger.warn(f"[{target_session_id}] WebSocket found but not connected for status message: {message_text}")
            # Optionally remove from active_websockets here if not handled elsewhere,
            # but disconnects are usually handled in the main websocket_endpoint.
        else:
            logger.warn(f"[{target_session_id}] No active WebSocket found for status message: {message_text}")

async def start_agent_session(session_id: str): # Changed to async def
    """Starts an ADK agent session."""
    logger.info(f"[{session_id}] Attempting to start agent session.")
    session = await session_service.create_session( # Added await
        app_name=APP_NAME,
        user_id=session_id,
        session_id=session_id,
    )
    runner = Runner(
        app_name=APP_NAME,
        agent=root_agent,
        session_service=session_service,
        artifact_service=artifact_service,
    )
    run_config = RunConfig(response_modalities=["TEXT"])
    live_request_queue = LiveRequestQueue()
    live_events = runner.run_live(
        session=session,
        live_request_queue=live_request_queue,
        run_config=run_config,
    )
    logger.info(f"[{session_id}] Agent session started. Live events queue created.")
    return live_events, live_request_queue

async def agent_to_client_messaging(websocket: WebSocket, live_events, session_id: str):
    """Handles messages from ADK agent to the WebSocket client."""
    # Outer try...except asyncio.CancelledError...finally retained
    try:
        async for event in live_events:
            message_to_send = None
            server_log_detail = None
            if event.turn_complete:
                server_log_detail = "Agent turn complete."
                message_to_send = {"type": "agent_turn_complete", "turn_complete": True}
            elif event.interrupted:
                server_log_detail = "Agent turn interrupted."
                message_to_send = {"type": "agent_interrupted", "interrupted": True}
            else:
                part: Part = (event.content and event.content.parts and event.content.parts[0])
                if part and part.text:
                    text = part.text
                    message_to_send = {"type": "agent_message", "message": text}

            if server_log_detail:
                logger.info(f"[{session_id}] AGENT->CLIENT_TASK: {server_log_detail}")
                # Removed call to send_server_log_to_client

            if message_to_send:
                # Inner try...except removed around send_text
                await websocket.send_text(json.dumps(message_to_send))
        logger.info(f"[{session_id}] Live events stream from agent finished.")
        # Removed call to send_server_log_to_client
    except asyncio.CancelledError:
        logger.info(f"[{session_id}] Agent-to-client messaging task cancelled.")
        raise # Re-raise CancelledError to be handled by asyncio.wait
    except Exception as e: # Catch other exceptions that were previously unhandled by inner try-except
        logger.error(f"[{session_id}] Unexpected error in agent_to_client_messaging: {e}", exc_info=True)
        # Removed call to send_server_log_to_client
    finally:
        logger.info(f"[{session_id}] Agent-to-client messaging task finished.")

async def client_to_agent_messaging(websocket: WebSocket, live_request_queue: LiveRequestQueue, session_id: str):
    """Handles messages from WebSocket client to the ADK agent."""
    # Outer try...except asyncio.CancelledError...finally retained
    try:
        while True:
            # Inner try...except removed
            text = await websocket.receive_text()
            logger.info(f"[{session_id}] CLIENT->AGENT_TASK: Received text: '{text}'")
            # Removed call to send_server_log_to_client
            content = Content(role="user", parts=[Part.from_text(text=text)])
            live_request_queue.send_content(content=content)
            # Removed call to send_server_log_to_client
    except WebSocketDisconnect: # Explicitly catch WebSocketDisconnect here now
        logger.info(f"[{session_id}] WebSocket disconnected by client.")
        live_request_queue.close()
        # Removed break, as exception will terminate loop
    except asyncio.CancelledError:
        logger.info(f"[{session_id}] Client-to-agent messaging task cancelled.")
        live_request_queue.close()
        raise # Re-raise CancelledError
    except Exception as e: # Catch other exceptions
         logger.error(f"[{session_id}] Error receiving/processing client message: {e}", exc_info=True)
         # Removed call to send_server_log_to_client
         live_request_queue.close()
         # Removed break
    finally:
        logger.info(f"[{session_id}] Client-to-agent messaging task finished.")

app = FastAPI(title=APP_NAME, version="0.1.0")

origins = ["*",]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    logger.info(f"Static files mounted from {STATIC_DIR}")
else:
    logger.error(f"Static directory or index.html not found at {STATIC_DIR}. Frontend may not load.")

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_running_loop()
    status_messenger.setup_status_messenger_async(loop)
    asyncio.create_task(status_message_broadcaster(), name="status_message_broadcaster_task")
    logger.info("Status message broadcaster task scheduled for startup.")

@app.get("/")
async def root_path():
    index_html_path = STATIC_DIR / "index.html"
    if index_html_path.is_file():
        return FileResponse(index_html_path)
    logger.error(f"index.html not found at {index_html_path}")
    return {"error": "index.html not found"}, 404

@app.websocket("/ws/{session_id_from_path}")
async def websocket_endpoint(websocket: WebSocket, session_id_from_path: str):
    session_id = session_id_from_path
    await websocket.accept()
    active_websockets[session_id] = websocket
    logger.info(f"[{session_id}] Client connected. Added to active list for status broadcasts.")
    # Removed call to send_server_log_to_client

    live_events = None
    live_request_queue = None
    agent_to_client_task = None
    client_to_agent_task = None
    context_var_token = None # Initialize token, will hold the reset token

    # Outer try...finally retained for cleanup
    try:
        context_var_token = current_websocket_session_id_var.set(session_id) # Set context var

        logger.info(f"[{session_id}] Initializing agent session backend.")
        # try...except removed around start_agent_session
        live_events, live_request_queue = await start_agent_session(session_id) # Added await
        # Removed call to send_server_log_to_client

        agent_to_client_task = asyncio.create_task(
            agent_to_client_messaging(websocket, live_events, session_id),
            name=f"agent_to_client_{session_id}"
        )
        client_to_agent_task = asyncio.create_task(
            client_to_agent_messaging(websocket, live_request_queue, session_id),
            name=f"client_to_agent_{session_id}"
        )
        # try...except removed around asyncio.wait
        done, pending = await asyncio.wait(
            {agent_to_client_task, client_to_agent_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            # This was error logging for tasks, if one errored, it would be caught by the broader try/except now
            # Or if it's a specific exception like WebSocketDisconnect, it's handled in the task or propagates
            if task.exception() and not isinstance(task.exception(), (WebSocketDisconnect, asyncio.CancelledError)):
                 exc = task.exception()
                 logger.error(f"[{session_id}] Task {task.get_name()} raised unhandled exception during wait: {exc}", exc_info=exc)
                 # Removed call to send_server_log_to_client
            else:
                 logger.info(f"[{session_id}] Task {task.get_name()} completed ({type(task.exception()).__name__ if task.exception() else 'normally'}).")
    except Exception as e: # This will now catch errors from start_agent_session and asyncio.wait
        logger.error(f"[{session_id}] Error in WebSocket endpoint: {e}", exc_info=True)
        # Removed call to send_server_log_to_client
    finally:
        if context_var_token: # Reset context var if it was set
            current_websocket_session_id_var.reset(context_var_token)

        logger.info(f"[{session_id}] Client disconnecting / cleaning up tasks...")
        removed_ws = active_websockets.pop(session_id, None)
        if removed_ws: logger.info(f"[{session_id}] WebSocket removed from active list.")

        tasks_to_cancel = []
        if 'pending' in locals() and pending: tasks_to_cancel.extend(list(pending))
        else:
            if agent_to_client_task and not agent_to_client_task.done(): tasks_to_cancel.append(agent_to_client_task)
            if client_to_agent_task and not client_to_agent_task.done(): tasks_to_cancel.append(client_to_agent_task)

        for task in tasks_to_cancel:
            if not task.done():
                logger.info(f"[{session_id}] Cancelling pending task: {task.get_name()}")
                task.cancel()
                try: await asyncio.wait_for(task, timeout=2.0)
                except asyncio.CancelledError: logger.info(f"[{session_id}] Task {task.get_name()} cancelled.")
                except asyncio.TimeoutError: logger.warning(f"[{session_id}] Task {task.get_name()} cancellation timeout.")
                except Exception as e_cancel: logger.error(f"[{session_id}] Error cancelling {task.get_name()}: {e_cancel}")
        
        if live_request_queue:
            try:
                logger.info(f"[{session_id}] Closing ADK live_request_queue.")
                live_request_queue.close()
            except Exception as e_q_close: logger.error(f"[{session_id}] Error closing live_request_queue: {e_q_close}")
        
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                logger.info(f"[{session_id}] Server explicitly closing WebSocket.")
                await websocket.close(code=1000)
        except Exception as e_ws_close: logger.debug(f"[{session_id}] Error during explicit WebSocket close (likely already closed): {e_ws_close}")
        logger.info(f"[{session_id}] Client cleanup finished.")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting Uvicorn server on http://0.0.0.0:{port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, app_dir=str(Path(__file__).parent))
