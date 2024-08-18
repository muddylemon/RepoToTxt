import os
import re
import ast
from github import Github
from tqdm import tqdm
from summarize_code import summarize_code


ADD_INSTRUCTIONS = False
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
SUMMARIZE_CODE = False
MAX_LINES_PER_FILE = 1200

if not GITHUB_TOKEN:
    raise ValueError("Please set the 'GITHUB_TOKEN' environment variable.")


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
                    file_contents += f"File: {
                        full_path}\nContent: Skipped binary or ignored file\n\n"
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
                                file_contents += f"Content:\n{
                                    decoded_content}\n\n"
                            except UnicodeDecodeError:
                                try:
                                    decoded_content = content.decoded_content.decode(
                                        'latin-1')
                                    if SUMMARIZE_CODE and content.name.endswith(('.py', '.js', '.java', '.cpp', '.c')):
                                        decoded_content = summarize_code(
                                            decoded_content)
                                    file_contents += f"Content (Latin-1 Decoded):\n{
                                        decoded_content}\n\n"
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
        repo_name, instructions, readme_content, repo_structure, file_contents = get_repo_contents(
            repo_url)
        output_filename = f'./outputs/{repo_name}_contents.txt'
        if not os.path.exists('./outputs'):
            os.makedirs('./outputs')
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
