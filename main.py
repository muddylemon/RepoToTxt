import os
import argparse
import re
from pathlib import Path
from github import Github
import logging
from tqdm import tqdm
from llm_compressor import LLMFriendlyCompressor


# Constants
ADD_INSTRUCTIONS = False
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
MAX_LINES_PER_FILE = 1200


# Extended default ignore lists
DEFAULT_IGNORED_DIRS = {
    # Version control
    '.git', '.svn', '.hg', '.bzr',

    # Package managers and dependencies
    'node_modules', 'bower_components', 'vendor', 'packages',
    '.npm', 'jspm_packages', 'pnpm-store', '.yarn',

    # Virtual environments
    'venv', '.venv', 'env', 'virtualenv', '.virtualenv',
    '.tox', '.direnv', '__pypackages__',

    # Python specific
    '__pycache__', '.pytest_cache', '.mypy_cache', '.coverage',

    # Build and output
    'build', 'dist', 'out', 'bin', 'obj', 'target',
    'Debug', 'Release', 'x64', 'x86', 'lib', '.cache',

    # IDE and editors
    '.idea', '.vscode', '.vs', '.fleet',

    # Environment and configuration
    '.settings', '.config', '.vagrant', '__snapshots__',
    '.terraform', '.next', '.nuxt',

    # Hidden directories
    '.github', '.husky', '.storybook'
}

DEFAULT_IGNORED_FILES = {
    # Documentation
    'README.md', 'README.txt', 'README',
    'LICENSE', 'LICENSE.txt', 'LICENSE.md',
    'CHANGELOG.md', 'CONTRIBUTING.md',

    # Lock files and metadata
    'package-lock.json', 'yarn.lock', 'bun.lockb',
    'pnpm-lock.yaml', 'poetry.lock', 'Pipfile.lock',
    'composer.lock', 'Gemfile.lock', 'cargo.lock',
    '.npmrc', '.yarnrc',

    # System files
    '.DS_Store', 'Thumbs.db', '.gitignore',

    # Config files
    'tsconfig.json', 'jsconfig.json',
    '.editorconfig', '.eslintcache', '.eslintrc',
    '.prettierrc', '.babelrc'
}

IGNORED_FILETYPES = (
    # Images
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp', '.tiff',
    '.tif', '.psd', '.raw', '.heif', '.jfif', '.pct', '.pic', '.pict', '.pntg',
    '.svgz',

    # Design files
    '.vsdx', '.vsd', '.vss', '.vst', '.vdx', '.vsx', '.vtx', '.vssx', '.vstx',
    '.vsw', '.vsta', '.ai', '.eps', '.indd',

    # Documents
    '.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt',

    # Audio/Video
    '.mp3', '.mp4', '.wav', '.avi', '.mov', '.flv', '.wmv', '.mkv',

    # Archives
    '.zip', '.rar', '.tar', '.gz', '.7z',

    # Compiled/minified files
    '.min.js', '.min.css', '.map',

    # Database and logs
    '.sqlite', '.db', '.log'
)


class GitignoreParser:
    def __init__(self, gitignore_path):
        self.patterns = []
        self.negated_patterns = []

        # Load patterns from gitignore
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue

                    # Handle negated patterns (those starting with !)
                    if line.startswith('!'):
                        pattern = line[1:].strip()
                        if pattern:
                            self.negated_patterns.append(
                                self._convert_pattern(pattern))
                    else:
                        self.patterns.append(self._convert_pattern(line))

    def _convert_pattern(self, pattern):
        """Convert gitignore pattern to a Python regex pattern."""
        # Remove leading and trailing slashes
        pattern = pattern.strip('/')

        # Replace ** with a placeholder
        pattern = pattern.replace('**', '{DOUBLE_STAR}')

        # Convert * to regex
        pattern = pattern.replace('*', '[^/]*')

        # Convert ? to regex
        pattern = pattern.replace('?', '[^/]')

        # Restore ** placeholder and convert to regex
        pattern = pattern.replace('{DOUBLE_STAR}', '.*')

        # Make sure pattern matches from start to end
        if not pattern.startswith('^'):
            pattern = '^' + pattern
        if not pattern.endswith('$'):
            pattern = pattern + '($|/.*$)'

        return re.compile(pattern)

    def matches(self, path):
        """Check if a path matches any gitignore pattern."""
        # Normalize path for matching
        path = path.replace('\\', '/')
        if path.startswith('./'):
            path = path[2:]

        # Check if path is ignored
        ignored = any(pattern.search(path) for pattern in self.patterns)

        # Check if path is negated (explicitly included)
        if ignored:
            negated = any(pattern.search(path)
                          for pattern in self.negated_patterns)
            return not negated

        return False


def is_binary_file(file_path):
    try:
        with open(file_path, 'tr') as check_file:
            check_file.read()
            return False
    except:
        return True


def load_gitignore_patterns(directory):
    """Load patterns from .gitignore file in the directory."""
    gitignore_path = os.path.join(directory, '.gitignore')
    if os.path.exists(gitignore_path):
        return GitignoreParser(gitignore_path)
    return None


def is_ignored_path(path, basename, gitignore_parser=None, custom_ignored_items=None):
    """Check if a path should be ignored based on multiple criteria."""
    # First check if the basename is in the default ignore list
    is_directory = os.path.isdir(path) if os.path.exists(
        path) else not os.path.splitext(basename)[1]

    if is_directory:
        if basename in DEFAULT_IGNORED_DIRS:
            return True
        if custom_ignored_items and basename in custom_ignored_items:
            return True
    else:
        if basename in DEFAULT_IGNORED_FILES:
            return True
        if basename.lower().endswith(IGNORED_FILETYPES):
            return True
        if custom_ignored_items and basename in custom_ignored_items:
            return True

    # Finally check gitignore patterns if available
    if gitignore_parser:
        relative_path = os.path.relpath(
            path, os.path.dirname(os.path.dirname(path)))
        if gitignore_parser.matches(relative_path):
            return True

    return False


# GitHub repository analysis functions
def get_readme_content(repo):
    try:
        readme = repo.get_contents("README.md")
        return readme.decoded_content.decode('utf-8')
    except:
        return "README not found."


def get_gitignore_from_repo(repo):
    """Attempt to get .gitignore content from a GitHub repository."""
    try:
        gitignore = repo.get_contents(".gitignore")
        content = gitignore.decoded_content.decode('utf-8')

        # Save to a temporary file for the parser to use
        temp_path = os.path.join(os.path.dirname(__file__), "temp_gitignore")
        with open(temp_path, 'w') as f:
            f.write(content)

        parser = GitignoreParser(temp_path)

        # Clean up
        os.remove(temp_path)

        return parser
    except:
        return None


def traverse_repo_iteratively(repo, custom_skips=None):
    # Try to get gitignore patterns
    gitignore_parser = get_gitignore_from_repo(repo)

    structure = ""
    dirs_to_visit = [("", repo.get_contents(""))]
    dirs_visited = set()

    while dirs_to_visit:
        path, contents = dirs_to_visit.pop()
        dirs_visited.add(path)
        for content in tqdm(contents, desc=f"Processing {path}", leave=False):
            # Check if should be ignored
            if is_ignored_path(content.path, content.name, gitignore_parser, custom_skips):
                continue

            if content.type == "dir":
                if content.path not in dirs_visited:
                    structure += f"{path}/{content.name}/\n"
                    dirs_to_visit.append(
                        (f"{path}/{content.name}", repo.get_contents(content.path)))
            else:
                structure += f"{path}/{content.name}\n"
    return structure


def get_file_contents_iteratively(repo, custom_skips=None):
    # Try to get gitignore patterns
    gitignore_parser = get_gitignore_from_repo(repo)

    file_contents = ""
    dirs_to_visit = [("", repo.get_contents(""))]
    dirs_visited = set()

    while dirs_to_visit:
        path, contents = dirs_to_visit.pop()
        dirs_visited.add(path)
        for content in tqdm(contents, desc=f"Downloading {path}", leave=False):
            # Check if should be ignored
            if is_ignored_path(content.path, content.name, gitignore_parser, custom_skips):
                continue

            if content.type == "dir":
                if content.path not in dirs_visited:
                    dirs_to_visit.append(
                        (f"{path}/{content.name}", repo.get_contents(content.path)))
            else:
                full_path = f"{path}/{content.name}"
                if is_binary_file(content.name):
                    file_contents += f"File: {full_path}\nContent: Skipped binary file\n\n"
                else:
                    file_contents += f"File: {full_path}\n"
                    try:
                        if content.encoding is None or content.encoding == 'none':
                            file_contents += "Content: Skipped due to missing encoding\n\n"
                        else:
                            try:
                                decoded_content = content.decoded_content.decode(
                                    'utf-8')
                                file_contents += f"Content: \n{decoded_content}\n\n"
                            except UnicodeDecodeError:
                                try:
                                    decoded_content = content.decoded_content.decode(
                                        'latin-1')
                                    file_contents += f"Content(Latin-1 Decoded): \n{decoded_content}\n\n"
                                except UnicodeDecodeError:
                                    file_contents += "Content: Skipped due to unsupported encoding\n\n"
                    except (AttributeError, UnicodeDecodeError):
                        file_contents += "Content: Skipped due to decoding error or missing decoded_content\n\n"
    return file_contents


def analyze_github_repo(repo_url, custom_skips=None):
    repo_name = repo_url.split('/')[-1]

    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(repo_url.replace('https://github.com/', ''))

    print(f"Fetching README for: {repo_name}")
    readme_content = get_readme_content(repo)

    print(f"\nFetching repository structure for: {repo_name}")
    repo_structure = f"Repository Structure: {repo_name}\n"
    repo_structure += traverse_repo_iteratively(repo, custom_skips)

    print(f"\nFetching file contents for: {repo_name}")
    file_contents = get_file_contents_iteratively(repo, custom_skips)

    return repo_name, readme_content, repo_structure, file_contents

# Local directory analysis functions


def get_directory_structure(directory, custom_skips=None):
    # Try to load gitignore patterns
    gitignore_parser = load_gitignore_patterns(directory)

    structure = []
    for root, dirs, files in os.walk(directory):
        # Filter out ignored directories in-place
        dirs[:] = [d for d in dirs if not is_ignored_path(
            os.path.join(root, d), d, gitignore_parser, custom_skips)]

        level = root.replace(directory, '').count(os.sep)
        indent = ' ' * 4 * level
        structure.append(f'{indent}{os.path.basename(root)}/')
        subindent = ' ' * 4 * (level + 1)

        # Filter files
        for file in files:
            if not is_ignored_path(os.path.join(root, file), file, gitignore_parser, custom_skips):
                structure.append(f'{subindent}{file}')

    return '\n'.join(structure)


def get_file_contents(directory, custom_skips=None):
    # Try to load gitignore patterns
    gitignore_parser = load_gitignore_patterns(directory)

    file_contents = ""
    for root, dirs, files in tqdm(os.walk(directory), desc="Processing files", unit="file"):
        # Filter out ignored directories in-place
        dirs[:] = [d for d in dirs if not is_ignored_path(
            os.path.join(root, d), d, gitignore_parser, custom_skips)]

        for file in files:
            file_path = os.path.join(root, file)

            # Skip ignored files
            if is_ignored_path(file_path, file, gitignore_parser, custom_skips):
                continue

            relative_path = os.path.relpath(file_path, directory)

            if is_binary_file(file_path):
                file_contents += f"File: {relative_path}\nContent: Skipped binary file\n\n"
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    file_contents += f"File: {relative_path}\nContent:\n{content}\n\n"
            except Exception as e:
                file_contents += f"File: {relative_path}\nError reading file: {str(e)}\n\n"

    return file_contents


def get_readme_content_local(directory):
    readme_files = ['README.md', 'README.txt', 'README']
    for readme in readme_files:
        readme_path = os.path.join(directory, readme)
        if os.path.exists(readme_path):
            with open(readme_path, 'r', encoding='utf-8') as f:
                return f.read()
    return "README not found."


def analyze_local_directory(directory, custom_skips=None):
    print(f"Analyzing directory: {directory}")

    readme_content = get_readme_content_local(directory)
    print("README content retrieved.")

    print("Generating directory structure...")
    dir_structure = get_directory_structure(directory, custom_skips)

    print("Processing file contents...")
    file_contents = get_file_contents(directory, custom_skips)

    return os.path.basename(os.path.abspath(directory)), readme_content, dir_structure, file_contents


def analyze_subdirectories(base_path, subdirs, custom_skips=None):
    results = []
    for subdir in subdirs:
        full_path = os.path.join(base_path, subdir)
        if not os.path.isdir(full_path):
            print(f"Warning: {full_path} is not a valid directory. Skipping.")
            continue

        print(f"\nAnalyzing subdirectory: {subdir}")
        name, readme_content, structure, file_contents = analyze_local_directory(
            full_path, custom_skips)
        results.append((subdir, name, readme_content,
                       structure, file_contents))

    return results


def analyze_input(input_path, subdirs=None, custom_skips=None, compression_level='none'):
    if input_path.startswith(('http://', 'https://')):
        if not GITHUB_TOKEN:
            raise ValueError(
                "Please set the 'GITHUB_TOKEN' environment variable for GitHub repository analysis.")
        return [analyze_github_repo(input_path, custom_skips)], compression_level
    elif os.path.isdir(input_path):
        if subdirs:
            return analyze_subdirectories(input_path, subdirs, custom_skips), compression_level
        else:
            return [analyze_local_directory(input_path, custom_skips)], compression_level
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
    parser.add_argument("--skip", nargs='+',
                        help="Files and folders to skip during analysis")
    parser.add_argument("--compress",
                        choices=['none', 'light', 'medium', 'heavy'],
                        default='none',
                        help="Compress output to be more LLM-friendly")
    parser.add_argument("--output", "-o",
                        help="Custom output filename (without extension)")
    parser.add_argument(
        "--compression-debug",
        action="store_true",
        help="Enable debug logging for compression")
    args = parser.parse_args()

    try:
        # Create outputs directory if it doesn't exist
        os.makedirs('outputs', exist_ok=True)

        # Analyze the repository or directory
        results, compression_level = analyze_input(
            args.input_path, args.subdirs, args.skip, args.compress)

        output_files = []
        for i, result in enumerate(results):
            # Determine output filename
            if args.output:
                if len(results) > 1:
                    # For multiple results, append an index if custom filename is provided
                    output_filename = f'outputs/{args.output}_{i+1}.txt'
                else:
                    # Single result with custom filename
                    output_filename = f'outputs/{args.output}.txt'
            else:
                # Default naming scheme
                if len(results) > 1:
                    subdir, name, readme_content, structure, file_contents = result
                    output_filename = f'outputs/{subdir}_analysis.txt'
                else:
                    name, readme_content, structure, file_contents = result
                    output_filename = f'outputs/{name}_analysis.txt'

            # Unpack the result based on the actual structure
            if len(results) > 1:
                subdir, name, readme_content, structure, file_contents = result
            else:
                name, readme_content, structure, file_contents = result

            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(f"README:\n{readme_content}\n\n")
                f.write(f"Structure:\n{structure}\n\n")
                f.write(f"File Contents:\n{file_contents}")

            output_files.append(output_filename)
            print(f"Analysis saved to '{output_filename}'.")

        if compression_level != 'none':
            compressor = LLMFriendlyCompressor()
            compressor.set_compression_level(compression_level)

            if args.compression_debug:
                compressor.logger.setLevel(logging.DEBUG)

            for filename in output_files:
                print(
                    f"Applying {compression_level} compression to {filename}...")

                # Read the file
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Get original file size
                original_size = os.path.getsize(filename)

                # Split into main sections
                readme_section = ""
                structure_section = ""
                file_contents_section = ""

                # Split the content into the three main sections
                if "README:" in content:
                    readme_and_rest = content.split("Structure:", 1)
                    readme_section = readme_and_rest[0].strip()

                    if len(readme_and_rest) > 1:
                        structure_and_files = readme_and_rest[1].split(
                            "File Contents:", 1)
                        structure_section = "Structure:" + \
                            structure_and_files[0].strip()

                        if len(structure_and_files) > 1:
                            file_contents_section = "File Contents:" + \
                                structure_and_files[1].strip()

                # Parse file content using regex for reliable extraction
                files_content = {}
                if file_contents_section:
                    # Use regex to find all file blocks
                    file_pattern = r'File: (.*?)(?:\r?\n)Content:(?:\r?\n)?([\s\S]*?)(?=(?:\r?\n){2}File: |$)'
                    matches = re.finditer(file_pattern, file_contents_section)

                    for match in matches:
                        file_path = match.group(1).strip()
                        file_content = match.group(2).strip()
                        files_content[file_path] = file_content

                    print(f"Found {len(files_content)} files to compress")

                # Compress files
                repo_summary, compressed_files = compressor.compress_repository(
                    files_content)

                # Rebuild file contents section
                compressed_file_contents = "File Contents:\n"
                for file_path, content in compressed_files.items():
                    compressed_file_contents += f"File: {file_path}\nContent:\n{content}\n\n"

                # Create the final output with repository summary
                compressed_output = f"{readme_section}\n\n"
                compressed_output += f"Repository Analysis Summary:\n{repo_summary}\n\n"
                compressed_output += f"{structure_section}\n\n"
                compressed_output += compressed_file_contents

                # Determine compressed output filename
                if args.output:
                    base_filename = os.path.basename(
                        filename).replace('.txt', '')
                    compressed_filename = f'outputs/{base_filename}_compressed_{compression_level}.txt'
                else:
                    compressed_filename = filename.replace(
                        '.txt', f'_compressed_{compression_level}.txt')

                # Write the compressed output
                with open(compressed_filename, 'w', encoding='utf-8') as f:
                    f.write(compressed_output)

                # Calculate compression stats
                compressed_size = os.path.getsize(compressed_filename)
                compression_ratio = compressed_size / original_size * 100

                print(
                    f"Compression complete: {len(compressed_files)} files processed")
                print(f"Original size: {original_size/1024:.1f} KB")
                print(f"Compressed size: {compressed_size/1024:.1f} KB")
                print(f"Compression ratio: {compression_ratio:.1f}%")
                print(f"Compressed analysis saved to '{compressed_filename}'")
            else:
                print("No compression applied")

    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please check the input and try again.")
