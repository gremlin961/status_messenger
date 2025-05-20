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
from status_messenger import get_status_messages, add_status_message # For application-level status updates



# Load .env file (e.g., for GOOGLE_CLOUD_PROJECT, etc. if agent needs them directly)
# The agent.py itself also loads .env and initializes Vertex AI.
load_dotenv(dotenv_path=Path(__file__).parent / '.env')

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


APP_NAME = "ADK Chat App" # Updated App Name
session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()

# Global store for active websockets, mapping session_id to WebSocket object
active_websockets: Dict[str, WebSocket] = {}

async def send_server_log_to_client(websocket: WebSocket, level: str, message: str, session_id: str):
    """Helper function to send a server diagnostic log message to the client."""
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            log_payload = {
                "type": "server_log",
                "level": level.upper(),
                "message": f"[{session_id}] {message}"
            }
            await websocket.send_text(json.dumps(log_payload))
        else:
            logger.debug(f"[SERVER LOG SEND - {session_id}] WebSocket not connected. Log not sent: {message}")
    except Exception as e:
        logger.error(f"[SERVER LOG SEND - {session_id}] Error sending log to client: {e}", exc_info=False)

async def broadcast_app_status_to_client(websocket: WebSocket, status_text: str, session_id: str):
    """Sends an application status message (type: 'status') to a single WebSocket client."""
    if websocket.client_state == WebSocketState.CONNECTED:
        try:
            payload = {"type": "status", "data": status_text} # As expected by index.html
            await websocket.send_text(json.dumps(payload))
            logger.info(f"[{session_id}] SENT_APP_STATUS_TO_CLIENT: {status_text}")
        except Exception as e:
            logger.error(f"[{session_id}] Error sending app status to client: {e}", exc_info=False)

async def application_status_monitor():
    """
    Periodically fetches messages from status_messenger and broadcasts new ones
    to all connected WebSocket clients.
    """
    logger.info("Application status monitor task starting.")
    try:
        if 'get_status_messages' in globals() and callable(get_status_messages):
            previously_broadcast_statuses = set(get_status_messages())
        else:
            logger.error("status_messenger.get_status_messages is not available. Status monitoring disabled.")
            return
    except Exception as e:
        logger.error(f"Error initializing status monitor with get_status_messages: {e}", exc_info=True)
        return

    while True:
        await asyncio.sleep(0.5) # Poll interval
        try:
            current_all_statuses = get_status_messages()
            new_unique_statuses_to_broadcast = set(current_all_statuses) - previously_broadcast_statuses

            if new_unique_statuses_to_broadcast:
                logger.debug(f"Found {len(new_unique_statuses_to_broadcast)} new app status(es) to broadcast.")
                for session_id, ws in list(active_websockets.items()):
                    if ws.client_state == WebSocketState.CONNECTED:
                        for status_msg in new_unique_statuses_to_broadcast:
                            await broadcast_app_status_to_client(ws, status_msg, session_id)
                    else:
                        logger.info(f"[{session_id}] Removing disconnected WebSocket from status broadcast list.")
                        active_websockets.pop(session_id, None)
                previously_broadcast_statuses.update(new_unique_statuses_to_broadcast)
        except Exception as e:
            logger.error(f"Error in application_status_monitor loop: {e}", exc_info=True)
            await asyncio.sleep(5) # Longer pause if error in loop

def start_agent_session(session_id: str):
    """Starts an ADK agent session."""
    logger.info(f"[{session_id}] Attempting to start agent session.")
    session = session_service.create_session(
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
    await send_server_log_to_client(websocket, "INFO", "Agent-to-client messaging task started.", session_id)
    try:
        async for event in live_events:
            message_to_send = None
            server_log_detail = None
            if event.turn_complete:
                server_log_detail = "Agent turn complete."
                message_to_send = {"type": "agent_turn_complete", "turn_complete": True} # Explicit type
            elif event.interrupted:
                server_log_detail = "Agent turn interrupted."
                message_to_send = {"type": "agent_interrupted", "interrupted": True} # Explicit type
            else:
                part: Part = (event.content and event.content.parts and event.content.parts[0])
                if part and part.text: # Ensure text exists
                    text = part.text
                    # server_log_detail = f"Sending agent message chunk (length: {len(text)})." # Can be verbose
                    message_to_send = {"type": "agent_message", "message": text} # Explicit type for chat

            if server_log_detail:
                logger.info(f"[{session_id}] AGENT->CLIENT_TASK: {server_log_detail}")
                await send_server_log_to_client(websocket, "DEBUG", server_log_detail, session_id)

            if message_to_send:
                try:
                    await websocket.send_text(json.dumps(message_to_send))
                except WebSocketDisconnect:
                    logger.warning(f"[{session_id}] Client disconnected during agent message send.")
                    return
                except Exception as e:
                    logger.error(f"[{session_id}] Error sending agent message to client: {e}", exc_info=True)
                    return
        logger.info(f"[{session_id}] Live events stream from agent finished.")
        await send_server_log_to_client(websocket, "INFO", "Live events stream from agent finished.", session_id)
    except asyncio.CancelledError:
        logger.info(f"[{session_id}] Agent-to-client messaging task cancelled.")
        raise
    except Exception as e:
        logger.error(f"[{session_id}] Unexpected error in agent-to-client messaging: {e}", exc_info=True)
        await send_server_log_to_client(websocket, "ERROR", f"Error in agent-to-client: {e}", session_id)
    finally:
        logger.info(f"[{session_id}] Agent-to-client messaging task finished.")

async def client_to_agent_messaging(websocket: WebSocket, live_request_queue: LiveRequestQueue, session_id: str):
    """Handles messages from WebSocket client to the ADK agent."""
    await send_server_log_to_client(websocket, "INFO", "Client-to-agent messaging task started.", session_id)
    try:
        while True:
            try:
                text = await websocket.receive_text()
                logger.info(f"[{session_id}] CLIENT->AGENT_TASK: Received text: '{text}'")
                await send_server_log_to_client(websocket, "INFO", f"Received text: '{text}'", session_id)
                content = Content(role="user", parts=[Part.from_text(text=text)])
                live_request_queue.send_content(content=content)
                await send_server_log_to_client(websocket, "DEBUG", "Content sent to agent's live request queue.", session_id)
            except WebSocketDisconnect:
                logger.info(f"[{session_id}] WebSocket disconnected by client.")
                live_request_queue.close()
                break
            except Exception as e:
                 logger.error(f"[{session_id}] Error receiving/processing client message: {e}", exc_info=True)
                 await send_server_log_to_client(websocket, "ERROR", f"Error processing client message: {e}", session_id)
                 live_request_queue.close()
                 break
    except asyncio.CancelledError:
        logger.info(f"[{session_id}] Client-to-agent messaging task cancelled.")
        live_request_queue.close()
        raise
    except Exception as e:
        logger.error(f"[{session_id}] Unexpected error in client-to-agent messaging: {e}", exc_info=True)
        await send_server_log_to_client(websocket, "ERROR", f"Error in client-to-agent: {e}", session_id)
        live_request_queue.close()
    finally:
        logger.info(f"[{session_id}] Client-to-agent messaging task finished.")

app = FastAPI(title=APP_NAME, version="0.1.0")

origins = ["*",] # Allow all for dev; restrict in prod
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
    asyncio.create_task(application_status_monitor(), name="app_status_monitor_task")
    logger.info("Application status monitor task scheduled for startup.")

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
    await send_server_log_to_client(websocket, "INFO", "Server accepted WebSocket connection.", session_id)

    live_events = None
    live_request_queue = None
    agent_to_client_task = None
    client_to_agent_task = None

    try:
        logger.info(f"[{session_id}] Initializing agent session backend.")
        live_events, live_request_queue = start_agent_session(session_id)
        await send_server_log_to_client(websocket, "INFO", "Agent session backend initialized.", session_id)

        agent_to_client_task = asyncio.create_task(
            agent_to_client_messaging(websocket, live_events, session_id),
            name=f"agent_to_client_{session_id}"
        )
        client_to_agent_task = asyncio.create_task(
            client_to_agent_messaging(websocket, live_request_queue, session_id),
            name=f"client_to_agent_{session_id}"
        )
        done, pending = await asyncio.wait(
            {agent_to_client_task, client_to_agent_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            if task.exception() and not isinstance(task.exception(), (WebSocketDisconnect, asyncio.CancelledError)):
                exc = task.exception()
                logger.error(f"[{session_id}] Task {task.get_name()} raised unhandled exception: {exc}", exc_info=exc)
                await send_server_log_to_client(websocket, "ERROR", f"Task {task.get_name()} error: {exc}", session_id)
            else:
                logger.info(f"[{session_id}] Task {task.get_name()} completed ({type(task.exception()).__name__ if task.exception() else 'normally'}).")
    except Exception as e:
        logger.error(f"[{session_id}] Error in WebSocket endpoint: {e}", exc_info=True)
        await send_server_log_to_client(websocket, "ERROR", f"WebSocket endpoint error: {e}", session_id)
    finally:
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
    # Correct app_dir should be the directory containing main.py, which is 'example_app'
    # If running `python example_app/main.py`, __file__ is 'example_app/main.py'
    # So Path(__file__).parent is 'example_app'
    # Uvicorn's `app_dir` should be where it looks for the module `main`
    # If main.py is in example_app, and we run `python example_app/main.py`,
    # then uvicorn.run("main:app", app_dir=str(Path(__file__).parent)) is correct.
    # However, the typical way to run is `uvicorn example_app.main:app` from the project root.
    # The provided uvicorn.run call is for direct execution `python example_app/main.py`.
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, app_dir=str(Path(__file__).parent))
