import asyncio
import threading
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List

# We'll assume 'status-messenger' is installed in the environment
# e.g., via `pip install -e ../status_messenger_py` or `pip install status-messenger`
try:
    from status_messenger import add_status_message, get_status_messages
except ImportError:
    print("Warning: 'status-messenger' package not found. Trying to import from relative path for dev.")
    import sys
    sys.path.append('../status_messenger_py') # Assuming 'status_messenger_py' is sibling to 'test'
    from status_messenger import add_status_message, get_status_messages

app = FastAPI()

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="static") # Serve index.html from static

# Global state for work thread (similar to Flask app context, but simpler for this example)
# In a more complex FastAPI app, you might use dependencies or a shared state object.
work_thread_holder = {"thread": None}

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/status", response_model=List[str])
async def get_status_endpoint():
    messages = get_status_messages()
    return messages

def do_simulated_work_sync():
    add_status_message("Starting simulated work (FastAPI)...")
    time.sleep(1)
    for i in range(1, 6):
        add_status_message(f"Processing step {i} of 5...")
        time.sleep(1.5)
    add_status_message("Simulated work completed!")
    time.sleep(2)
    add_status_message("Ready for new work or displaying results.")

@app.post("/simulate_work")
async def trigger_work_endpoint():
    if work_thread_holder["thread"] and work_thread_holder["thread"].is_alive():
        raise HTTPException(status_code=409, detail="Work is already in progress.")

    add_status_message("Received request to start work (FastAPI).")
    # FastAPI typically uses asyncio for background tasks, but since `add_status_message`
    # is synchronous and manipulates a global list, a simple thread is still okay here
    # for demonstration. For true async background tasks, use FastAPI's BackgroundTasks.
    thread = threading.Thread(target=do_simulated_work_sync)
    work_thread_holder["thread"] = thread
    thread.start()
    return {"message": "Simulated work started in background (FastAPI)."}

if __name__ == "__main__":
    # This block is for running with `python app.py`.
    # For production, you'd use Uvicorn directly: `uvicorn app:app --reload --port 8000`
    # Uvicorn is an ASGI server.
    import uvicorn
    add_status_message("Application started (FastAPI). Waiting for actions.")
    uvicorn.run(app, host="0.0.0.0", port=8000)
