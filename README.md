# status_messenger

This repository contains the source code for the `status_messenger` module, available for both Python and JavaScript.

`status_messenger` is designed to facilitate sending notifications and messages to a user, particularly within a multi-agent workflow utilizing Google's Agent Development Kit (ADK).

## Overview

The primary goal of this project is to demonstrate how `status_messenger` can be integrated into applications to provide clear and timely status updates to users.

## Examples

Example implementations showcasing the usage of `status_messenger` can be found in the `example_app/` directory:

*   **`example_app/main.py`**: A Python FastAPI application demonstrating server-side integration. It sends various message types, including status updates, over a WebSocket connection.
*   **`example_app/static/` directory**: Contains the client-side example:
    *   `index.html`: The main HTML page for the example application.
    *   `script.js`: Handles the primary chat functionality and user interactions. It now integrates the `status_messenger` JavaScript library (loaded via CDN) to display status messages received from the server in a dedicated area.

## Running the Example Application

The `example_app/` can be easily run using the provided shell script. This script handles the necessary setup for the Google Cloud Project ID and launches the Uvicorn server.

1.  **Navigate to the example app directory:**
    ```bash
    cd example_app
    ```

2.  **Make the script executable (if you haven't already):**
    ```bash
    chmod +x run_app.sh
    ```

3.  **Run the script:**
    ```bash
    ./run_app.sh
    ```
    The script will guide you if the `.env` file for the agent needs to be configured with your Google Cloud Project ID.
    Once running, the application will be accessible at `http://localhost:8000`.

## Modules

### Python

The Python module can be found in the `python/` directory. It includes the `status_messenger` library and setup instructions.

### JavaScript

The JavaScript package is located in the `javascript/` directory. It provides the necessary files and instructions for integrating `status_messenger` into JavaScript-based projects.

## Getting Started

Please refer to the README files within the `python/` and `javascript/` directories for specific installation and usage instructions for each module.
