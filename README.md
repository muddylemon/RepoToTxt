# RepoToTxt

Gather all the info your LLM needs to understand your repo in one command.

## Prerequisites

Create a virtual environment and then run:

```bash
pip install -r ./requirements.txt
```

For GitHub repositories, create a personal access token on Github and add it to your environment variables:

### Powershell

```powershell
$env:GITHUB_TOKEN="your-token"
```

### Bash

```bash
export GITHUB_TOKEN="your-token"
```

## How To Use

Run the script with either a GitHub repository URL or a path to a local directory as an argument:

```bash
python main.py <github_url_or_local_path>
```

### For GitHub Repositories:

Use the full GitHub URL, e.g.:

```bash
python main.py https://github.com/username/repo-name
```

### For Local Directories:

Use the path to the local directory, e.g.:

```bash
python main.py ../RepoToTxt
```

Your results will be saved as `{REPO_NAME}_analysis.txt` in the `outputs/` directory.

## Configuration

You can update the value of `ADD_INSTRUCTIONS` in the script if you wish to add LLM instructions to the file.

## Project Structure

```
RepoToTxt/
    analyze_directory.py
    requirements.txt
    summarize_code.py
    repototxt.py
    llm_instructions.txt
    main.py
    outputs/
        {REPO_NAME}_analysis.txt
```

## Note

This tool supports both GitHub repositories and local directories. It automatically detects the input type based on the provided argument and processes accordingly.