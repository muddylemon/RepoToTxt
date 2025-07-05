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
def get_readme_content(repo, component_metrics):
    try:
        readme = repo.get_contents("README.md")
        content = readme.decoded_content.decode('utf-8')
        component_metrics.append({'type': 'readme_header', 'path': 'README_header', 'char_count': len("README:\n")})
        component_metrics.append({'type': 'readme_content', 'path': 'README.md', 'char_count': len(content)})
        component_metrics.append({'type': 'readme_footer', 'path': 'README_footer', 'char_count': len("\n\n")})
        return content
    except:
        readme_not_found_text = "README not found."
        component_metrics.append({'type': 'readme_header', 'path': 'README_header', 'char_count': len("README:\n")})
        component_metrics.append({'type': 'readme_content', 'path': 'README.md', 'char_count': len(readme_not_found_text)})
        component_metrics.append({'type': 'readme_footer', 'path': 'README_footer', 'char_count': len("\n\n")})
        return readme_not_found_text


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


def traverse_repo_iteratively(repo, component_metrics, custom_skips=None):
    # Try to get gitignore patterns
    gitignore_parser = get_gitignore_from_repo(repo)

    structure_parts = []
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
                    structure_parts.append(f"{path}/{content.name}/\n")
                    dirs_to_visit.append(
                        (f"{path}/{content.name}", repo.get_contents(content.path)))
            else:
                structure_parts.append(f"{path}/{content.name}\n")

    structure_str = "".join(structure_parts)
    # Note: The "Repository Structure: {repo_name}\n" part is added in analyze_github_repo
    # So, here we only account for the structure string itself and its surrounding newlines if we consider it part of this component.
    # For consistency with local analysis, let's assume analyze_github_repo handles the main header for structure.
    # The get_directory_structure adds "Structure:\n" and "\n\n". We'll ensure analyze_github_repo does similarly for metrics.
    component_metrics.append({'type': 'structure_content', 'path': 'Structure', 'char_count': len(structure_str)})
    return structure_str


def get_file_contents_iteratively(repo, component_metrics, custom_skips=None):
    # Try to get gitignore patterns
    gitignore_parser = get_gitignore_from_repo(repo)

    file_contents_parts = []
    component_metrics.append({'type': 'file_section_header', 'path': 'File Contents_header', 'char_count': len("File Contents:\n")})
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
                full_path = f"{path}/{content.name}" # full_path here is like 'subfolder/file.txt'
                # For GitHub, content.path is the full path from repo root, content.name is just file name.
                # We use content.path for metrics consistency with local paths.

                header_text = f"File: {content.path}\nContent:\n" # Use content.path
                content_text = ""
                footer_text = "\n\n"

                # Heuristic: GitHub API's content.name doesn't have path, so is_binary_file(content.name) is problematic if it expects a full path.
                # However, is_binary_file opens the file by its name, so it should be fine if it's just checking extension or magic numbers.
                # For safety, let's assume is_binary_file is okay with just name, but if it needs path, this might need adjustment.
                # The current is_binary_file tries to open it, which won't work with just a name for GitHub content.
                # We'll rely on IGNORED_FILETYPES for binary common types for GitHub, and skip the is_binary_file check here.
                # A better is_binary_file for repo content would check content.type or common binary extensions.
                # For now, let's assume if it's not text, it's problematic.

                if content.name.lower().endswith(IGNORED_FILETYPES): # Check against common binary extensions
                    content_text = "Skipped binary file (based on extension)"
                else:
                    try:
                        if content.encoding is None or content.encoding == 'none':
                            content_text = "Skipped due to missing encoding"
                        elif content.decoded_content is None:
                            content_text = "Skipped (no decoded_content)"
                        else:
                            try:
                                content_text = content.decoded_content.decode('utf-8')
                            except UnicodeDecodeError:
                                try:
                                    content_text = content.decoded_content.decode('latin-1')
                                except UnicodeDecodeError:
                                    content_text = "Skipped due to unsupported encoding"
                    except AttributeError: # E.g. if content object doesn't have these attributes
                        content_text = "Skipped due to attribute error accessing content/encoding"

                component_metrics.append({'type': 'file_header', 'path': content.path, 'char_count': len(header_text)})
                component_metrics.append({'type': 'file_content', 'path': content.path, 'char_count': len(content_text)})
                component_metrics.append({'type': 'file_footer', 'path': content.path, 'char_count': len(footer_text)})

                file_contents_parts.append(header_text + content_text + footer_text)

    return "".join(file_contents_parts)


def analyze_github_repo(repo_url, component_metrics, custom_skips=None):
    repo_name = repo_url.split('/')[-1]

    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(repo_url.replace('https://github.com/', ''))

    print(f"Fetching README for: {repo_name}")
    readme_content = get_readme_content(repo, component_metrics) # Pass component_metrics

    print(f"\nFetching repository structure for: {repo_name}")
    # Add metrics for the structure header that analyze_github_repo itself adds
    structure_header_text = f"Repository Structure: {repo_name}\n"
    component_metrics.append({'type': 'structure_header', 'path': 'Structure_header', 'char_count': len(structure_header_text)})

    # traverse_repo_iteratively will add structure_content
    repo_structure_str_content = traverse_repo_iteratively(repo, component_metrics, custom_skips)
    repo_structure = structure_header_text + repo_structure_str_content

    # Add metrics for the footer of the structure section
    structure_footer_text = "\n\n"
    component_metrics.append({'type': 'structure_footer', 'path': 'Structure_footer', 'char_count': len(structure_footer_text)})


    print(f"\nFetching file contents for: {repo_name}")
    # get_file_contents_iteratively will add file_section_header, and individual file metrics
    file_contents = get_file_contents_iteratively(repo, component_metrics, custom_skips)

    return repo_name, readme_content, repo_structure, file_contents

# Local directory analysis functions


def get_directory_structure(directory, component_metrics, custom_skips=None):
    # Try to load gitignore patterns
    gitignore_parser = load_gitignore_patterns(directory)

    structure = []
    for root, dirs, files in os.walk(directory):
        # Filter out ignored directories in-place
        dirs[:] = [d for d in dirs if not is_ignored_path(
            os.path.join(root, d), d, gitignore_parser, custom_skips)]

        # Corrected level calculation
        norm_directory = os.path.normpath(directory)
        norm_root = os.path.normpath(root)

        if norm_root == norm_directory:
            level = 0
        else:
            # Calculate depth based on path components
            rel_path = os.path.relpath(norm_root, norm_directory)
            level = len(Path(rel_path).parts)

        indent = '    ' * level  # Indent for the directory name itself

        # Add current directory to structure
        # For the very first root, display its name. For sub-roots, display their name.
        structure.append(f'{indent}{os.path.basename(norm_root)}/')

        # Indent for files within this directory
        subindent = '    ' * (level + 1)

        # Filter files
        for file_name in files: # Renamed 'file' to 'file_name' to avoid conflict with 'file' type
            if not is_ignored_path(os.path.join(root, file_name), file_name, gitignore_parser, custom_skips):
                structure.append(f'{subindent}{file_name}')

    structure_str = '\n'.join(structure)
    component_metrics.append({'type': 'structure_header', 'path': 'Structure_header', 'char_count': len("Structure:\n")})
    component_metrics.append({'type': 'structure_content', 'path': 'Structure', 'char_count': len(structure_str)})
    component_metrics.append({'type': 'structure_footer', 'path': 'Structure_footer', 'char_count': len("\n\n")})
    return structure_str


def get_file_contents(directory, component_metrics, custom_skips=None):
    # Try to load gitignore patterns
    gitignore_parser = load_gitignore_patterns(directory)

    file_contents_parts = []
    component_metrics.append({'type': 'file_section_header', 'path': 'File Contents_header', 'char_count': len("File Contents:\n")})
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

            header_text = f"File: {relative_path}\nContent:\n"
            content_text = ""
            footer_text = "\n\n"

            if is_binary_file(file_path):
                content_text = "Skipped binary file"
            else:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content_text = f.read()
                except Exception as e:
                    content_text = f"Error reading file: {str(e)}"

            component_metrics.append({'type': 'file_header', 'path': relative_path, 'char_count': len(header_text)})
            component_metrics.append({'type': 'file_content', 'path': relative_path, 'char_count': len(content_text)})
            component_metrics.append({'type': 'file_footer', 'path': relative_path, 'char_count': len(footer_text)})

            file_contents_parts.append(header_text + content_text + footer_text)

    return "".join(file_contents_parts)


def get_readme_content_local(directory, component_metrics):
    readme_files = ['README.md', 'README.txt', 'README']
    for readme in readme_files:
        readme_path = os.path.join(directory, readme)
        if os.path.exists(readme_path):
            with open(readme_path, 'r', encoding='utf-8') as f:
                content = f.read()
                component_metrics.append({'type': 'readme_header', 'path': 'README_header', 'char_count': len("README:\n")})
                component_metrics.append({'type': 'readme_content', 'path': readme, 'char_count': len(content)})
                component_metrics.append({'type': 'readme_footer', 'path': 'README_footer', 'char_count': len("\n\n")})
                return content
    readme_not_found_text = "README not found."
    component_metrics.append({'type': 'readme_header', 'path': 'README_header', 'char_count': len("README:\n")})
    component_metrics.append({'type': 'readme_content', 'path': 'README.md', 'char_count': len(readme_not_found_text)})
    component_metrics.append({'type': 'readme_footer', 'path': 'README_footer', 'char_count': len("\n\n")})
    return readme_not_found_text


def analyze_local_directory(directory, component_metrics, custom_skips=None):
    print(f"Analyzing directory: {directory}")

    readme_content = get_readme_content_local(directory, component_metrics)
    print("README content retrieved.")

    print("Generating directory structure...")
    dir_structure = get_directory_structure(directory, component_metrics, custom_skips)

    print("Processing file contents...")
    file_contents = get_file_contents(directory, component_metrics, custom_skips)

    return os.path.basename(os.path.abspath(directory)), readme_content, dir_structure, file_contents


def analyze_subdirectories(base_path, subdirs, component_metrics_list_ref, custom_skips=None):
    results = []
    for subdir_idx, subdir in enumerate(subdirs):
        # Each subdir analysis gets its own component_metrics list
        current_subdir_metrics = []
        component_metrics_list_ref.append(current_subdir_metrics)

        full_path = os.path.join(base_path, subdir)
        if not os.path.isdir(full_path):
            print(f"Warning: {full_path} is not a valid directory. Skipping.")
            # Add an empty metrics list for consistency if needed, or handle appropriately
            continue

        print(f"\nAnalyzing subdirectory: {subdir}")
        name, readme_content, structure, file_contents = analyze_local_directory(
            full_path, current_subdir_metrics, custom_skips)
        results.append((subdir, name, readme_content,
                       structure, file_contents))

    return results


def analyze_input(input_path, component_metrics_list_ref, subdirs=None, custom_skips=None, compression_level='none'):
    if input_path.startswith(('http://', 'https://')):
        if not GITHUB_TOKEN:
            raise ValueError(
                "Please set the 'GITHUB_TOKEN' environment variable for GitHub repository analysis.")
        # Each repo analysis gets its own component_metrics list
        current_repo_metrics = []
        component_metrics_list_ref.append(current_repo_metrics)
        analysis_result = analyze_github_repo(input_path, current_repo_metrics, custom_skips)
        return [analysis_result], compression_level
    elif os.path.isdir(input_path):
        if subdirs:
            # analyze_subdirectories will populate component_metrics_list_ref
            return analyze_subdirectories(input_path, subdirs, component_metrics_list_ref, custom_skips), compression_level
        else:
            # Single local directory analysis
            current_dir_metrics = []
            component_metrics_list_ref.append(current_dir_metrics)
            analysis_result = analyze_local_directory(input_path, current_dir_metrics, custom_skips)
            return [analysis_result], compression_level
    else:
        raise ValueError(
            "Invalid input. Please provide a valid GitHub repository URL or local directory path.")


def calculate_and_print_metrics(component_metrics, output_filename):
    if not component_metrics:
        print("No component metrics available to calculate.")
        return

    total_char_count_from_components = sum(c.get('char_count', 0) for c in component_metrics)

    try:
        total_size_on_disk = os.path.getsize(output_filename)
    except FileNotFoundError:
        print(f"Error: Output file {output_filename} not found. Cannot determine total size on disk.")
        total_size_on_disk = 0 # Or handle as a more critical error
    except Exception as e:
        print(f"Error getting size of {output_filename}: {e}")
        total_size_on_disk = 0


    print("\nOutput Metrics:")
    print("-----------------------------------")
    if total_size_on_disk > 0:
        print(f"Total Output File Size: {total_size_on_disk / 1024:.2f} KB ({total_size_on_disk} bytes)")
    else:
        print(f"Total Output File Size: N/A (file not found, empty, or error accessing)")

    print(f"Total Characters (from components): {total_char_count_from_components} chars")
    print("\nContent Breakdown (based on character counts):")

    # --- Calculate size for primary components: README, Structure, Files ---
    readme_total_chars = 0
    structure_total_chars = 0
    files_section_total_chars = 0 # Includes headers like "File Contents:\n" and individual file headers/footers

    for component in component_metrics:
        ct_type = component.get('type', '')
        char_c = component.get('char_count', 0)
        if ct_type.startswith('readme'):
            readme_total_chars += char_c
        elif ct_type.startswith('structure'):
            structure_total_chars += char_c
        elif ct_type.startswith('file_section_header') or \
             ct_type.startswith('file_header') or \
             ct_type.startswith('file_content') or \
             ct_type.startswith('file_footer'):
            files_section_total_chars += char_c

    denominator_for_percent = total_char_count_from_components if total_char_count_from_components > 0 else 1

    has_readme = any(c.get('type','').startswith('readme') for c in component_metrics)
    has_structure = any(c.get('type','').startswith('structure') for c in component_metrics)
    has_files = any(c.get('type','').startswith('file_') for c in component_metrics)

    if has_readme:
        percent_readme = (readme_total_chars / denominator_for_percent) * 100
        print(f"- README section: {readme_total_chars} chars ({percent_readme:.2f}%)")

    if has_structure:
        percent_structure = (structure_total_chars / denominator_for_percent) * 100
        print(f"- Structure section: {structure_total_chars} chars ({percent_structure:.2f}%)")

    if has_files:
        percent_files_section = (files_section_total_chars / denominator_for_percent) * 100
        print(f"- Files section (total): {files_section_total_chars} chars ({percent_files_section:.2f}%)")

        # --- Detailed breakdown for individual files and directories ---
        # Aggregate content sizes by file path
        file_content_sizes = {} # path: char_count
        for component in component_metrics:
            if component.get('type') == 'file_content': # Only actual content of files for this breakdown
                path = component.get('path', 'Unknown_Path')
                file_content_sizes[path] = file_content_sizes.get(path, 0) + component.get('char_count', 0)

        # Aggregate content sizes by directory
        directory_content_sizes = {} # dir_path: char_count
        for path, size in file_content_sizes.items():
            dir_name = os.path.dirname(path)
            if not dir_name:
                dir_name = "." # Files in root
            directory_content_sizes[dir_name] = directory_content_sizes.get(dir_name, 0) + size

        if directory_content_sizes:
            print("    - Directory Content Breakdown (based on sum of file_content components):")
            sorted_dirs = sorted(directory_content_sizes.items(), key=lambda item: item[0]) # Sort by name
            for dir_name, dir_size in sorted_dirs:
                # Percentage of this directory's content relative to total characters from all components
                percent_dir_overall = (dir_size / denominator_for_percent) * 100
                print(f"        - {dir_name if dir_name != '.' else 'Root Directory Files'}/: {dir_size} chars ({percent_dir_overall:.2f}% of total)")

        # Optionally, print individual file content sizes (can be verbose)
        # print("    - Individual File Content Breakdown (file_content only):")
        # sorted_files = sorted(file_content_sizes.items(), key=lambda item: item[0])
        # for path, size in sorted_files:
        #     percent_file_overall = (size / denominator_for_percent) * 100
        #     print(f"        - {path}: {size} chars ({percent_file_overall:.2f}% of total)")

    print("-----------------------------------")


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

        all_component_metrics = [] # This will be a list of lists (one list per result)
        # Analyze the repository or directory
        results, compression_level = analyze_input(
            args.input_path, all_component_metrics, args.subdirs, args.skip, args.compress)

        output_files = []
        # Ensure all_component_metrics has the same length as results
        # If analyze_input had to skip some subdirs, it should have appended empty lists or placeholders.
        # For simplicity, we'll assume they align or that analyze_input ensures alignment.
        # A more robust solution might involve analyze_input returning metrics alongside results.

        for i, result in enumerate(results):
            current_result_metrics = all_component_metrics[i] if i < len(all_component_metrics) else []

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

            # Calculate and print metrics for the current output file
            if current_result_metrics: # Only print if metrics were collected
                calculate_and_print_metrics(current_result_metrics, output_filename)
            else:
                print(f"No metrics collected for {output_filename}")


        if compression_level != 'none':
            # Metrics for compressed files could also be added, but that's out of scope for the current request.
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
