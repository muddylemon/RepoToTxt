#!/usr/bin/env python3

import os
import sys
import subprocess

def ensure_dependencies():
    try:
        import github
        import tqdm
    except ImportError:
        print("Required dependencies not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyGithub", "tqdm"])

ensure_dependencies()

import re
import ast
from github import Github
from tqdm import tqdm

try:
    import re
    import ast
    from github import Github
    from tqdm import tqdm
except ImportError as e:
    print(f"Error: Required module not found. {e}")
    print("Please install the required modules using:")
    print("pip install PyGithub tqdm")
    sys.exit(1)


ADD_INSTRUCTIONS = False
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
SUMMARIZE_CODE = False
MAX_LINES_PER_FILE = 1200

if not GITHUB_TOKEN:
    raise ValueError("Please set the 'GITHUB_TOKEN' environment variable.")


def summarize_code(content, max_lines=MAX_LINES_PER_FILE):
    def calculate_importance(line):
        importance = 0
        if re.match(r'^\s*(def|class|import|from)', line):
            importance += 5
        if re.search(r'(TODO|FIXME|NOTE|IMPORTANT)', line):
            importance += 3
        if re.match(r'^\s*#', line):  # Comments
            importance += 2
        if re.match(r'^\s*[A-Z_]+\s*=', line):  # Constants
            importance += 2
        return importance

    lines = content.split('\n')
    if len(lines) <= max_lines:
        return content

    try:
        # Extract docstrings and important comments
        tree = ast.parse(content)
        docstrings = [
            node.body[0].value.value  # Use .value instead of .s
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module))
            and isinstance(node.body[0], ast.Expr)
            # Use ast.Constant instead of ast.Str
            and isinstance(node.body[0].value, ast.Constant)
            # Ensure it's a string
            and isinstance(node.body[0].value.value, str)
        ]
    except SyntaxError:
        # If parsing fails, fall back to line-based importance
        docstrings = []

    # Combine docstrings with other lines for importance calculation
    all_lines = [(i, line, calculate_importance(line))
                 for i, line in enumerate(lines)]
    all_lines.extend((None, docstring, 4)
                     # High importance for docstrings
                     for docstring in docstrings)

    # Sort by importance and select top lines
    selected_lines = sorted(all_lines, key=lambda x: x[2], reverse=True)[
        :max_lines]

    # Sort selected lines back into original order
    selected_lines = sorted(
        [line for line in selected_lines if line[0] is not None], key=lambda x: x[0])

    # Ensure context by including surrounding lines
    context_lines = set()
    for i, _, _ in selected_lines:
        context_lines.update(range(max(0, i-1), min(len(lines), i+2)))

    # Combine selected and context lines
    final_lines = sorted(
        set([i for i, _, _ in selected_lines] + list(context_lines)))

    # Reconstruct the summarized content
    summarized_content = "\n".join(lines[i] for i in final_lines)

    # Add header and footer
    header = "# Code summary (truncated for brevity)\n"
    footer = "\n# ... (truncated) ..."

    return header + summarized_content + footer


def get_readme_content(repo):
    """
    Retrieve the content of the README file.
    """
    try:
        readme = repo.get_contents("README.md")
        return readme.decoded_content.decode('utf-8')
    except:
        return "README not found."


def traverse_repo_iteratively(repo):
    """
    Traverse the repository iteratively to avoid recursion limits for large repositories.
    """
    structure = ""
    dirs_to_visit = [("", repo.get_contents(""))]
    dirs_visited = set()

    while dirs_to_visit:
        path, contents = dirs_to_visit.pop()
        dirs_visited.add(path)
        for content in tqdm(contents, desc=f"Processing {path}", leave=False):
            if content.type == "dir":
                if content.path not in dirs_visited:
                    structure += f"{path}/{content.name}/\n"
                    dirs_to_visit.append(
                        (f"{path}/{content.name}", repo.get_contents(content.path)))
            else:
                structure += f"{path}/{content.name}\n"
    return structure


def is_binary_file(file_name):
    binary_extensions = [
        '.pyc', '.exe', '.dll', '.so', '.dylib', '.zip', '.tar.gz',
        '.pdf', '.jpg', '.jpeg', '.png', '.svg', '.ico',
        '.woff', '.woff2', '.ttf', '.eot',
        '.mp4', '.avi', '.mov', '.wmv',
        '.wav', '.mp3', '.ogg', '.flac',
        '.bmp', '.gif', '.webp', '.tiff',
        '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.min.js', '.min.css'
    ]
    return any(file_name.lower().endswith(ext) for ext in binary_extensions)


def is_ignored_file(file_name):
    ignored_files = [
        '__pycache__', '.git', 'node_modules', 'venv', '.venv', 'env',
        'README.md', 'README.txt', 'README',
        'LICENSE', 'LICENSE.txt', 'LICENSE.md',
        'package-lock.json', 'yarn.lock', 'bun.lockb',
        '.DS_Store', 'Thumbs.db'
    ]
    return any(ignored in file_name for ignored in ignored_files)


def get_file_contents_iteratively(repo):
    file_contents = ""
    dirs_to_visit = [("", repo.get_contents(""))]
    dirs_visited = set()

    while dirs_to_visit:
        path, contents = dirs_to_visit.pop()
        dirs_visited.add(path)
        for content in tqdm(contents, desc=f"Downloading {path}", leave=False):
            if content.type == "dir":
                if content.path not in dirs_visited:
                    dirs_to_visit.append(
                        (f"{path}/{content.name}", repo.get_contents(content.path)))
            else:
                full_path = f"{path}/{content.name}"
                if is_binary_file(content.name) or is_ignored_file(full_path):
                    file_contents += f"""File: {
                        full_path}\nContent: Skipped binary or ignored file\n\n"""
                else:
                    file_contents += f"File: {full_path}\n"
                    try:
                        if content.encoding is None or content.encoding == 'none':
                            file_contents += "Content: Skipped due to missing encoding\n\n"
                        else:
                            try:
                                decoded_content = content.decoded_content.decode(
                                    'utf-8')
                                if SUMMARIZE_CODE and content.name.endswith(('.py', '.js', '.java', '.cpp', '.c')):
                                    decoded_content = summarize_code(
                                        decoded_content)
                                file_contents += f"""Content:\n{
                                    decoded_content}\n\n"""
                            except UnicodeDecodeError:
                                try:
                                    decoded_content = content.decoded_content.decode(
                                        'latin-1')
                                    if SUMMARIZE_CODE and content.name.endswith(('.py', '.js', '.java', '.cpp', '.c')):
                                        decoded_content = summarize_code(
                                            decoded_content)
                                    file_contents += f"""Content (Latin-1 Decoded):\n{
                                        decoded_content}\n\n"""
                                except UnicodeDecodeError:
                                    file_contents += "Content: Skipped due to unsupported encoding\n\n"
                    except (AttributeError, UnicodeDecodeError):
                        file_contents += "Content: Skipped due to decoding error or missing decoded_content\n\n"
    return file_contents

def get_repo_contents(repo_url):
    """
    Main function to get repository contents.
    """
    repo_name = repo_url.split('/')[-1]

    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(repo_url.replace('https://github.com/', ''))

    print(f"Fetching README for: {repo_name}")
    readme_content = get_readme_content(repo)

    print(f"\nFetching repository structure for: {repo_name}")
    repo_structure = f"Repository Structure: {repo_name}\n"
    repo_structure += traverse_repo_iteratively(repo)

    print(f"\nFetching file contents for: {repo_name}")
    file_contents = get_file_contents_iteratively(repo)

    instructions = ""
    if ADD_INSTRUCTIONS:
        with open('llm_instructions.txt', 'r') as f:
            instructions = f.read()

    return repo_name, instructions, readme_content, repo_structure, file_contents

if __name__ == '__main__':
    repo_url = input("Please enter the GitHub repository URL: ")
    try:
        repo_name, instructions, readme_content, repo_structure, file_contents = get_repo_contents(repo_url)
        output_filename = f'{repo_name}_contents.txt'
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(instructions)
            f.write(f"README:\n{readme_content}\n\n")
            f.write(repo_structure)
            f.write('\n\n')
            f.write(file_contents)
        print(f"Repository contents saved to '{output_filename}'.")
    except ValueError as ve:
        print(f"Error: {ve}")
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please check the repository URL and try again.")
        