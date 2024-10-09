import os
import argparse
from github import Github
from tqdm import tqdm


# Constants
ADD_INSTRUCTIONS = False
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
MAX_LINES_PER_FILE = 1200


def is_binary_file(file_path):
    try:
        with open(file_path, 'tr') as check_file:
            check_file.read()
            return False
    except:
        return True


def is_ignored_directory(dir_name):
    ignored_dirs = {
        '.git', 'node_modules', 'venv', '.venv', 'env',
        '__pycache__', 'build', 'dist', '.idea', '.vscode'
    }
    return dir_name in ignored_dirs


def is_ignored_file(file_name):
    ignored_files = {
        'README.md', 'README.txt', 'README',
        'LICENSE', 'LICENSE.txt', 'LICENSE.md',
        'package-lock.json', 'yarn.lock', 'bun.lockb',
        '.DS_Store', 'Thumbs.db', '.gitignore'
    }
    return file_name in ignored_files


def is_ignored_filetype(file_name):
    ignored_filetypes = (
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp', '.tiff',
        '.tif', '.psd', '.raw', '.heif', '.indd', '.ai', '.eps', '.pdf', '.jfif',
        '.pct', '.pic', '.pict', '.pntg', '.svgz', '.vsdx', '.vsd', '.vss', '.vst',
        '.vdx', '.vsx', '.vtx', '.vdx', '.vsx', '.vtx', '.vst', '.vssx', '.vstx',
        '.vsw', '.vsta'
    )
    return file_name.lower().endswith(ignored_filetypes)


# GitHub repository analysis functions
def get_readme_content(repo):
    try:
        readme = repo.get_contents("README.md")
        return readme.decoded_content.decode('utf-8')
    except:
        return "README not found."


def traverse_repo_iteratively(repo):
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
                                file_contents += f"Content:\n{
                                    decoded_content}\n\n"
                            except UnicodeDecodeError:
                                try:
                                    decoded_content = content.decoded_content.decode(
                                        'latin-1')
                                    file_contents += f"Content (Latin-1 Decoded):\n{
                                        decoded_content}\n\n"
                                except UnicodeDecodeError:
                                    file_contents += "Content: Skipped due to unsupported encoding\n\n"
                    except (AttributeError, UnicodeDecodeError):
                        file_contents += "Content: Skipped due to decoding error or missing decoded_content\n\n"
    return file_contents


def analyze_github_repo(repo_url):
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

    return repo_name, readme_content, repo_structure, file_contents

# Local directory analysis functions


def get_directory_structure(directory):
    structure = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not is_ignored_directory(d)]
        level = root.replace(directory, '').count(os.sep)
        indent = ' ' * 4 * level
        structure.append(f'{indent}{os.path.basename(root)}/')
        subindent = ' ' * 4 * (level + 1)
        for file in files:
            if not is_ignored_file(file):
                structure.append(f'{subindent}{file}')
    return '\n'.join(structure)


def get_file_contents(directory):
    file_contents = ""
    for root, dirs, files in tqdm(os.walk(directory), desc="Processing files", unit="file"):
        dirs[:] = [d for d in dirs if not is_ignored_directory(d)]
        for file in files:
            if is_ignored_file(file):
                continue
            if is_ignored_filetype(file):
                continue

            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, directory)

            if is_binary_file(file_path):
                file_contents += f"File: {
                    relative_path}\nContent: Skipped binary file\n\n"
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    file_contents += f"File: {
                        relative_path}\nContent:\n{content}\n\n"
            except Exception as e:
                file_contents += f"File: {
                    relative_path}\nError reading file: {str(e)}\n\n"

    return file_contents


def get_readme_content_local(directory):
    readme_files = ['README.md', 'README.txt', 'README']
    for readme in readme_files:
        readme_path = os.path.join(directory, readme)
        if os.path.exists(readme_path):
            with open(readme_path, 'r', encoding='utf-8') as f:
                return f.read()
    return "README not found."


def analyze_local_directory(directory):
    print(f"Analyzing directory: {directory}")

    readme_content = get_readme_content_local(directory)
    print("README content retrieved.")

    print("Generating directory structure...")
    dir_structure = get_directory_structure(directory)

    print("Processing file contents...")
    file_contents = get_file_contents(directory)

    return os.path.basename(os.path.abspath(directory)), readme_content, dir_structure, file_contents


def analyze_subdirectories(base_path, subdirs):
    results = []
    for subdir in subdirs:
        full_path = os.path.join(base_path, subdir)
        if not os.path.isdir(full_path):
            print(f"Warning: {full_path} is not a valid directory. Skipping.")
            continue

        print(f"\nAnalyzing subdirectory: {subdir}")
        name, readme_content, structure, file_contents = analyze_local_directory(
            full_path)
        results.append((subdir, name, readme_content,
                       structure, file_contents))

    return results


def analyze_input(input_path, subdirs=None):
    if input_path.startswith(('http://', 'https://')):
        if not GITHUB_TOKEN:
            raise ValueError(
                "Please set the 'GITHUB_TOKEN' environment variable for GitHub repository analysis.")
        return [analyze_github_repo(input_path)]
    elif os.path.isdir(input_path):
        if subdirs:
            return analyze_subdirectories(input_path, subdirs)
        else:
            return [analyze_local_directory(input_path)]
    else:
        raise ValueError(
            "Invalid input. Please provide a valid GitHub repository URL or local directory path.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Analyze a GitHub repository or local directory.")
    parser.add_argument(
        "input_path", help="GitHub repository URL or path to the local directory to analyze")
    parser.add_argument("subdirs", nargs='*',
                        help="Subdirectories to analyze (optional)")
    args = parser.parse_args()

    try:
        results = analyze_input(args.input_path, args.subdirs)

        for result in results:
            if len(results) > 1:
                subdir, name, readme_content, structure, file_contents = result
                output_filename = f'outputs/{subdir}_analysis.txt'
            else:
                name, readme_content, structure, file_contents = result
                output_filename = f'outputs/{name}_analysis.txt'

            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(f"README:\n{readme_content}\n\n")
                f.write(f"Structure:\n{structure}\n\n")
                f.write(f"File Contents:\n{file_contents}")

            print(f"Analysis saved to '{output_filename}'.")
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please check the input and try again.")
