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

from setuptools import setup, find_packages

# Read the contents of your README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="status_messenger",
    version="0.3.1", # Should match __version__ in __init__.py
    author="Cline - AI Software Engineer",
    author_email="your_email@example.com", # Replace with a placeholder or actual email
    description="A simple package to manage and display status messages.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your_username/status_messenger", # Replace with a placeholder or actual URL
    packages=['status_messenger'], # Explicitly list the package
    # packages=find_packages(), # Alternative if status_messenger is a top-level dir for setup.py
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha", # Or "4 - Beta", "5 - Production/Stable"
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires='>=3.7', # Specify your Python version compatibility
    install_requires=[
        "google-cloud-pubsub>=2.0.0", # Added for GCP Pub/Sub integration
        # Add any dependencies here, e.g., "flask>=2.0" if you include the server
    ],
    # If you want to include a simple Flask server as an optional extra:
    # extras_require={
    #     "server": ["flask>=2.0"],
    # },
    # entry_points={
    #     'console_scripts': [
    #         'status-server=status_messenger.server:main', # If you create a server script
    #     ],
    # },
)
