# RepoToTxt 📁✨

**Turn your codebase into a single text file for LLM analysis—with just one command!**

RepoToTxt makes it super easy to analyze your repositories with AI tools. Feed your entire project to your favorite LLM without the hassle of copying files one by one.

## 🚀 Quick Start

### Prerequisites

First, create a virtual environment and install the required packages:

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

For GitHub repositories, you'll need a personal access token:

**On Windows (PowerShell):**

```powershell
$env:GITHUB_TOKEN="your-token-here"
```

**On macOS/Linux:**

```bash
export GITHUB_TOKEN="your-token-here"
```

### Basic Usage

RepoToTxt is flexible and works with both GitHub repositories and local projects:

```bash
# Analyze a GitHub repo
python main.py https://github.com/username/repository

# Analyze a local directory
python main.py /path/to/your/project
```

Your analysis will be saved in the `outputs` folder as `{repo_name}_analysis.txt`.

## 🔍 Advanced Usage

### Analyze Specific Subdirectories

Working on a large project? Focus on just the parts you need:

```bash
python main.py /path/to/base/directory frontend backend utils
```

This creates separate analysis files for each subdirectory:

- `outputs/frontend_analysis.txt`
- `outputs/backend_analysis.txt`
- `outputs/utils_analysis.txt`

### Skip Files and Folders

Got files you want to exclude? Use the `--skip` flag:

```bash
python main.py /path/to/directory --skip node_modules temp_files old
```

### Compression Options

Large codebases can be too much for LLMs to handle. Use compression to make your analysis more digestible:

```bash
# Light compression - preserves most details
python main.py /path/to/directory --compress light

# Medium compression - balanced approach
python main.py /path/to/directory --compress medium

# Heavy compression - maximum token reduction
python main.py /path/to/directory --compress heavy
```

Compression works by:

- Summarizing lengthy docstrings and comments
- Reducing repetitive code sections
- Focusing on the most important files and functions
- Preserving the overall structure and core functionality

### Custom Output Filename

Want to specify your own output filename?

```bash
python main.py /path/to/directory --output my-special-analysis
```

This saves the result to `outputs/my-special-analysis.txt`.

### Debug Compression

If you're curious about how compression is affecting your files:

```bash
python main.py /path/to/directory --compress medium --compression-debug
```

## 🛠️ Configuration

Want to add custom instructions for your LLM? Open `main.py` and update the `ADD_INSTRUCTIONS` variable.

## 📊 Output Structure

Your analysis file includes:

1. **README content** - Project overview and setup instructions
2. **Repository structure** - Directory and file organization
3. **File contents** - The actual code (with optional summarization for large files)

## 📝 Notes

- Make sure `GITHUB_TOKEN` is set correctly when analyzing GitHub repositories
- Binary files and very large files are automatically skipped or summarized
- The tool respects `.gitignore` patterns in your repository

## 🤝 Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## 📜 License

[Include your license information here]
