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

"""
Status Messenger Package
------------------------

Provides a simple way to manage and display status messages,
typically for agentic applications or long-running processes
where updates need to be communicated to a UI.
It also supports publishing structured agent events to GCP Pub/Sub.
"""

from .messenger import (
    add_status_message,
    setup_status_messenger_async,
    stream_status_updates,
    publish_agent_event, # Added for Pub/Sub
    current_websocket_session_id_var # Exporting for direct use if needed by advanced server setups
)

__all__ = [
    "add_status_message",
    "setup_status_messenger_async",
    "stream_status_updates",
    "publish_agent_event", # Added for Pub/Sub
    "current_websocket_session_id_var",
]

__version__ = "0.3.1" # Incremented version due to new feature
