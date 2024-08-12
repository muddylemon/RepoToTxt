RepoToTxt
===

Gather all the info your LLM needs to understand your repo in one command.

## Prerequisites

Create a virtual environment and then run:

`pip install -r ./requirements.txt`

Create a personal access token on Github and add it to your environment variables.

### Powershell

`$env:GITHUB_TOKEN="your-token"`

### Bash

`export GITHUB_TOKEN="your-token"`

## How To Use

Run `python main.py` and paste your target repos github url when prompted

Your results will be saved as `{REPO_NAME}_context.txt`

Update the value of `ADD_INSTRUCTIONS` if you wish to add LLM instructions to the file.
