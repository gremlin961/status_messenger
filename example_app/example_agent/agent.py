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

# Example Agent Workflow using Google's ADK
# 
# This notebook provides an example of building an agentic workflow with Google's new ADK. 
# For more information please visit  https://google.github.io/adk-docs/



# Vertex AI Modules
import vertexai
from vertexai.preview.generative_models import GenerativeModel, GenerationConfig, Part, Tool, ChatSession, FunctionDeclaration, grounding, GenerationResponse
from vertexai.preview import rag # Import the RAG (Retrieval-Augmented Generation) module

# Vertex Agent Modules
from google.adk.agents import Agent # Base class for creating agents
from google.adk.runners import Runner # Class to run agent interactions
from google.adk.sessions import InMemorySessionService # Simple session management (non-persistent)
from google.adk.artifacts import InMemoryArtifactService, GcsArtifactService # In-memory artifact storage
from google.adk.tools.agent_tool import AgentTool # Wrapper to use one agent as a tool for another
from google.adk.tools import ToolContext
from google.adk.tools import load_artifacts, google_search

# Vertex GenAI Modules (Alternative/Legacy way to interact with Gemini, used here for types)
import google.genai
from google.genai import types as types # Used for structuring messages (Content, Part)

# Google Cloud AI Platform Modules
from google.cloud import aiplatform_v1beta1 as aiplatform # Specific client for RAG management features


# Other Python Modules
#import base64 # Not used in the final script
#from IPython.display import Markdown # Not used in the final script
import asyncio # For running asynchronous agent interactions
import requests # For making HTTP requests (to the mock ticket server)
import os # For interacting with the operating system (paths, environment variables)
from typing import List, Dict, TypedDict, Any # For type hinting
import json # For working with JSON data (API requests/responses)
from urllib.parse import urlparse # For parsing GCS bucket URIs
import warnings # For suppressing warnings
import logging # For controlling logging output
import mimetypes # For detecting mime types of files
import io
from dotenv import load_dotenv

from status_messenger import add_status_message, get_status_messages


# --- Configuration ---
load_dotenv()
project_id = os.environ.get('GOOGLE_CLOUD_PROJECT') # Your GCP Project ID
location = os.environ.get('GOOGLE_CLOUD_LOCATION') # Vertex AI RAG location (can be global for certain setups)
region = os.environ.get('GOOGLE_CLOUD_REGION') # Your GCP region for Vertex AI resources and GCS bucket




# Ignore all warnings
warnings.filterwarnings("ignore")
# Set logging level to ERROR to suppress informational messages
logging.basicConfig(level=logging.ERROR)





# --- Environment Setup ---
# Set environment variables required by some Google Cloud libraries
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1" # Instructs the google.genai library to use Vertex AI backend
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = region

# --- Initialize Vertex AI SDK ---
# Initialize the Vertex AI client library with project and location/region details
vertexai.init(project=project_id, location=region)







# --- Agent Tool Definitions ---
# @title Define Tools for creating a ticket, adding notes to a ticket, add a file to the session, and getting the GCS URI

# Tool function to create a support ticket via a mock API
def status_message(message: str) -> str:
    """
    Sends a status message to the user

    Args:
        message: A string containing the message to display to the user
    """
    add_status_message(message)

    

# -- Reasoning Agent ---
# This agent's role is to generate troubleshooting steps based on document content
# (which is expected to be in the context after add_file_to_session is called).
reasoning_agent = None
reasoning_agent = Agent(
    model="gemini-2.5-pro-preview-05-06", # Advanced model for complex tasks and reasoning
    #model="gemini-2.5-flash-preview-04-17", # Alternate Model that can be used to help address resource constraints with more advanced models
    name="reasoning_agent",
    instruction=
    """
        You are a research expert for your company. You will be provided with a request to research something and you will return your findings.
        
        You will use the `status_message` tool to provide status updates as you proceed with your research.
        
        An example workflow would be:
        1: You will be provided with a topic or question to research
        2: Use the `status_message` tool to provide the status "Reasearching `the provided question or topic` now. Please wait..."
        3: Use the `status_message` tool to provide the status "Research complete, generating the response now"
        4: Use the `status_message` tool to provide the status "Sending resutls back to the root agent. Please wait."
        5: Return the response to the calling agent
        
    """,
    description="Performs reasearch related to a provided question or topic.",
    tools=[
        status_message, # Make the status_message function available as a tool
    ],
)



# --- Root Agent Definition ---
# @title Define the Root Agent with Sub-Agents

# Initialize root agent variables
root_agent = None
runner_root = None # Initialize runner variable (although runner is created later)

    # Define the root agent (coordinator)
search_agent_team = Agent(
    name="search_support_agent",    # Name for the root agent
    #model="gemini-2.0-flash-001", # Model for the root agent (orchestration)
    model="gemini-2.0-flash-exp", # Model that supports Audio input and output 
    description="The main coordinator agent. Handles user requests and delegates tasks to specialist sub-agents and tools.", # Description (useful if this agent were itself a sub-agent)
    instruction=                  # The core instructions defining the workflow
    """
        You are the lead support coordinator agent. Your goal is to understand the customer's question or topic, and then delegate to the appropriate agent or tool.

        You have access to specialized tools and sub-agents:
        1. AgentTool `reasoning_agent`: Provide the user's question or topic. This agent will research the topic or question and provide a detailed response. The `reasoning_agent`'s response will be streamed directly to the user.

        Your workflow:
        1. Start by greeting the user.
        2. Ask no more than 1-2 clarifying questions to understand their research request.
        3. Once the request is clear, inform the user you will begin the research (e.g., "Okay, I'll start researching that for you. Please wait a moment.").
        4. Call the `reasoning_agent` with the user's research request.
        5. Use the `status_message` tool to provide the status "Resutls from the research agent received. Please wait."
        6. Provide the full audit report from the `research_agent` to the user. Do not summarize this information, just return the full report exactly as you receive it. 
        7. Use the `status_message` tool to provide the status "Research complete."
        8. Ask the user if there is anything else you can help with.
       
    """,
    tools=[
        AgentTool(agent=reasoning_agent), # Make the reasoning_agent available as a tool
        status_message, # Make the status_message function available as a tool
    ],

)

# Assign the created agent to the root_agent variable for clarity in the next step
root_agent = search_agent_team
