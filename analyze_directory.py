#!/usr/bin/env python3

import os
import sys
import argparse
from tqdm import tqdm

MAX_LINES_PER_FILE = 1200
SUMMARIZE_CODE = False

try:
    from summarize_code import summarize_code
except ImportError:
    print("Warning: summarize_code module not found. Code summarization will be disabled.")
    # Dummy function if summarize_code is not available
    def summarize_code(x): return x


def is_binary_file(file_path):
    """Check if file is binary."""
    try:
        with open(file_path, 'tr') as check_file:
            check_file.read()
            return False
    except:
        return True


def is_ignored_directory(dir_name):
    """Check if directory should be ignored."""
    ignored_dirs = {
        '.git', 'node_modules', 'venv', '.venv', 'env',
        '__pycache__', 'build', 'dist', '.idea', '.vscode'
    }
    return dir_name in ignored_dirs


def is_ignored_file(file_name):
    """Check if file should be ignored."""
    ignored_files = {
        'README.md', 'README.txt', 'README',
        'LICENSE', 'LICENSE.txt', 'LICENSE.md',
        'package-lock.json', 'yarn.lock', 'bun.lockb',
        '.DS_Store', 'Thumbs.db', '.gitignore'
    }
    return file_name in ignored_files


def get_directory_structure(directory):
    """Get the directory structure."""
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
    """Get contents of all files in the directory."""
    file_contents = ""
    for root, dirs, files in tqdm(os.walk(directory), desc="Processing files", unit="file"):
        dirs[:] = [d for d in dirs if not is_ignored_directory(d)]
        for file in files:
            if is_ignored_file(file):
                continue
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, directory)

            if is_binary_file(file_path):
                file_contents += f"File: {relative_path}\nContent: Skipped binary file\n\n"
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if SUMMARIZE_CODE and file.endswith(('.py', '.js', '.java', '.cpp', '.c')):
                        content = summarize_code(content)
                    file_contents += f"File: {relative_path}\nContent:\n{content}\n\n"
            except Exception as e:
                file_contents += f"File: {relative_path}\nError reading file: {str(e)}\n\n"

    return file_contents


def get_readme_content(directory):
    """Get content of README file if it exists."""
    readme_files = ['README.md', 'README.txt', 'README']
    for readme in readme_files:
        readme_path = os.path.join(directory, readme)
        if os.path.exists(readme_path):
            with open(readme_path, 'r', encoding='utf-8') as f:
                return f.read()
    return "README not found."


def analyze_directory(directory):
    """Main function to analyze the directory."""
    print(f"Analyzing directory: {directory}")

    readme_content = get_readme_content(directory)
    print("README content retrieved.")

    print("Generating directory structure...")
    dir_structure = get_directory_structure(directory)

    print("Processing file contents...")
    file_contents = get_file_contents(directory)

    return readme_content, dir_structure, file_contents


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Analyze a local directory and save its contents.")
    parser.add_argument("directory", help="Path to the directory to analyze")
    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: {args.directory} is not a valid directory.")
        sys.exit(1)

    try:
        readme_content, dir_structure, file_contents = analyze_directory(
            args.directory)

        # Use the base name of the directory as the prefix for the output file
        dir_name = os.path.basename(os.path.abspath(args.directory))
        output_filename = f'{dir_name}_analysis.txt'

        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(f"README:\n{readme_content}\n\n")
            f.write(f"Directory Structure:\n{dir_structure}\n\n")
            f.write(f"File Contents:\n{file_contents}")

        print(f"Directory analysis saved to '{output_filename}'.")
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please check the directory path and try again.")
