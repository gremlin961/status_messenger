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
"""

from .messenger import AGENT_STATUS_MESSAGES, add_status_message, get_status_messages

__all__ = [
    "AGENT_STATUS_MESSAGES",
    "add_status_message",
    "get_status_messages",
]

__version__ = "0.1.0"
