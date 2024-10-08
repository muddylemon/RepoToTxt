# RepoToTxt

Gather all the info your LLM needs to understand your repo in one command.

## Prerequisites

Create a virtual environment and then run:

```
pip install -r ./requirements.txt
```

Create a personal access token on Github and add it to your environment variables.

### Powershell

```
$env:GITHUB_TOKEN="your-token"
```

### Bash

```
export GITHUB_TOKEN="your-token"
```

## How To Use

### Analyzing a GitHub Repository

Run `python main.py` and paste your target repo's GitHub URL when prompted:

```
python main.py https://github.com/username/repository
```

Your results will be saved as `outputs/{REPO_NAME}_analysis.txt`

### Analyzing a Local Directory

To analyze a local directory, provide the path to the directory:

```
python main.py /path/to/your/directory
```

### Analyzing Specific Subdirectories

You can now analyze specific subdirectories within a local directory. Use the following syntax:

```
python main.py /path/to/base/directory [subdir1] [subdir2] [subdir3]
```

For example:

```
python main.py ../mycoolapp/cloud checkout functions admin
```

This will create separate analysis files for each subdirectory in the `outputs` folder:

- `outputs/checkout_analysis.txt`
- `outputs/functions_analysis.txt`
- `outputs/admin_analysis.txt`

## Configuration

Update the value of `ADD_INSTRUCTIONS` in `main.py` if you wish to add LLM instructions to the file.

## Output

The analysis output includes:

1. README content
2. Repository/directory structure
3. File contents (with optional summarization for large files)

## Note

When analyzing GitHub repositories, ensure that your `GITHUB_TOKEN` environment variable is set correctly.
