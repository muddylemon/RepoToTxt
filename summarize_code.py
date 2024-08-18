import re
import ast
from collections import Counter

MAX_LINES_PER_FILE = 1200


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
