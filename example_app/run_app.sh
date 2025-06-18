#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ENV_FILE="$SCRIPT_DIR/example_agent/.env"
ENV_TEMPLATE="$SCRIPT_DIR/example_agent/env_template"
PLACEHOLDER_PROJECT_LINE="GOOGLE_CLOUD_PROJECT=YOUR_GPC_PROJECT_ID" # Line to find and replace
PLACEHOLDER_PUBSUB_ENABLED_LINE="STATUS_MESSENGER_PUBSUB_ENABLED=false" # Line to find and replace
PLACEHOLDER_PUBSUB_TOPIC_LINE="STATUS_MESSENGER_PUBSUB_TOPIC_ID=YOUR_PUBSUB_TOPIC_ID" # Line to find and replace


echo "--------------------------------------------------"
echo "Status Messenger - Example App Launcher"
echo "--------------------------------------------------"
echo "Script directory: $SCRIPT_DIR"
echo "Env file path: $ENV_FILE"
echo "Env template path: $ENV_TEMPLATE"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
  echo ".env file not found at $ENV_FILE."
  read -p "Please enter your Google Cloud Project ID: " USER_GCP_PROJECT_ID

  if [ -z "$USER_GCP_PROJECT_ID" ]; then
    echo "No Project ID entered. Exiting."
    exit 1
  fi

  echo "Creating .env file from template..."
  cp "$ENV_TEMPLATE" "$ENV_FILE"
  if [ $? -ne 0 ]; then
    echo "Error: Failed to copy template to .env file. Please check permissions."
    exit 1
  fi

  echo "Updating GOOGLE_CLOUD_PROJECT in .env file..."
  # Use sed to replace the specific line. Works on macOS and Linux.
  # The | character is used as a delimiter for sed to avoid issues if paths contain /
  sed -i '' "s|$PLACEHOLDER_PROJECT_LINE|GOOGLE_CLOUD_PROJECT=$USER_GCP_PROJECT_ID|" "$ENV_FILE"
  echo ".env file created and configured with Project ID: $USER_GCP_PROJECT_ID"

  # Ask about Pub/Sub only if .env file was just created
  echo "--------------------------------------------------"
  read -p "Do you want to enable Pub/Sub for status messages? (y/n): " ENABLE_PUBSUB
  if [[ "$ENABLE_PUBSUB" == "y" || "$ENABLE_PUBSUB" == "Y" ]]; then
    read -p "Please enter your Google Cloud Pub/Sub Topic ID: " PUBSUB_TOPIC_ID
    if [ -z "$PUBSUB_TOPIC_ID" ]; then
      echo "No Pub/Sub Topic ID entered. Pub/Sub will not be enabled."
    else
      echo "Enabling Pub/Sub and configuring topic ID: $PUBSUB_TOPIC_ID"
      # Append Pub/Sub settings to .env file
      # Ensure there's a newline before appending if the file doesn't end with one
      if [ -s "$ENV_FILE" ] && [ "$(tail -c1 "$ENV_FILE"; echo x)" != $'\nx' ]; then
        echo "" >> "$ENV_FILE"
      fi
      sed -i '' "s|$PLACEHOLDER_PUBSUB_ENABLED_LINE|STATUS_MESSENGER_PUBSUB_ENABLED=true|" "$ENV_FILE"
      sed -i '' "s|$PLACEHOLDER_PUBSUB_TOPIC_LINE|STATUS_MESSENGER_PUBSUB_TOPIC_ID=$PUBSUB_TOPIC_ID|" "$ENV_FILE"
      echo "Pub/Sub enabled and configured in $ENV_FILE."
    fi
  else
    echo "Pub/Sub not enabled."
  fi
else
  echo ".env file already exists at $ENV_FILE. Using existing configuration."
fi

echo "--------------------------------------------------"
echo "Starting Uvicorn server for main:app..."
echo "Access the application at http://localhost:8000"
echo "Press Ctrl+C to stop the server."
echo "--------------------------------------------------"

# Function to clean up and exit
cleanup() {
  echo "" # Newline
  echo "--------------------------------------------------"
  echo "Shutting down Uvicorn server..."
  echo "--------------------------------------------------"
  # Kill the Uvicorn process; pkill will find it by name
  # The trap will catch SIGINT (Ctrl+C) and SIGTERM
  # Uvicorn should handle these signals gracefully, but this is a fallback.
  if [ ! -z "$UVICORN_PID" ]; then
    kill $UVICORN_PID
    wait $UVICORN_PID 2>/dev/null
  fi
  exit 0
}

# Trap termination signals
trap cleanup SIGINT SIGTERM

# Navigate to the script's directory (example_app) to run uvicorn
cd "$SCRIPT_DIR" || exit

# Launch Uvicorn
# The command from main.py's uvicorn.run is:
# uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, app_dir=str(Path(__file__).parent))
# This translates to running `uvicorn main:app --reload --port 8000 --host 0.0.0.0` from within the example_app directory.
# The --app-dir is implicit when running from the directory containing main.py.
uvicorn main:app --reload --port 8000 --host 0.0.0.0 &
UVICORN_PID=$!

# Wait for Uvicorn process to exit
wait $UVICORN_PID
# Call cleanup in case Uvicorn exits on its own (e.g. due to an error)
cleanup
