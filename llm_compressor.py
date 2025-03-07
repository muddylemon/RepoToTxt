import os
import re
import ast
import json
import hashlib
from collections import Counter
import logging


class LLMFriendlyCompressor:
    """
    Compresses code and content in ways that preserve meaning for LLMs
    while reducing token count.
    """

    def __init__(self):
        # Configuration - with more aggressive defaults
        # Compress files with at least this many lines
        self.min_lines_for_compression = 15
        self.import_summary_threshold = 5    # Summarize imports if more than this many
        self.comment_compression_ratio = 0.5  # How aggressively to compress comments
        # Minimum occurrences to consider something duplicated
        self.duplicate_threshold = 3
        self.max_lines_to_keep = 500         # Maximum lines to keep for any file
        self.max_class_methods_to_show = 3   # For heavy compression
        self.extremely_aggressive = False    # Ultra compression mode

        # Patterns
        self.docstring_pattern = re.compile(
            r'([\'\"])\1\1[\s\S]*?\1{3}|\"\"\"[\s\S]*?\"\"\"|\'\'\'[\s\S]*?\'\'\'')
        self.comment_pattern = re.compile(r'^\s*#.*$', re.MULTILINE)
        self.import_pattern = re.compile(
            r'^(?:import|from)\s+.*$', re.MULTILINE)
        self.blank_line_pattern = re.compile(r'\n\s*\n\s*\n+')

        # Language detection
        self.language_extensions = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'react',
            '.tsx': 'react',
            '.java': 'java',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.cs': 'csharp',
            '.cpp': 'cpp',
            '.c': 'c',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.html': 'html',
            '.css': 'css',
            '.json': 'json',
            '.md': 'markdown',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.sh': 'bash',
            '.sql': 'sql'
        }

        # Special compression handlers by language
        self.language_handlers = {
            'python': self.compress_python,
            'javascript': self.compress_javascript,
            'typescript': self.compress_javascript,
            'json': self.compress_json,
            'html': self.compress_html,
            'css': self.compress_css,
            'markdown': self.compress_markdown,
        }

        # Enable debug mode
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger('LLMCompressor')

    def set_compression_level(self, level):
        """Configure compression based on the level."""
        if level == 'light':
            self.comment_compression_ratio = 0.8
            self.min_lines_for_compression = 40
            self.duplicate_threshold = 8
            self.import_summary_threshold = 10
            self.max_lines_to_keep = 1000
            self.max_class_methods_to_show = 8
            self.extremely_aggressive = False
        elif level == 'medium':
            self.comment_compression_ratio = 0.6
            self.min_lines_for_compression = 25
            self.duplicate_threshold = 5
            self.import_summary_threshold = 8
            self.max_lines_to_keep = 750
            self.max_class_methods_to_show = 5
            self.extremely_aggressive = False
        elif level == 'heavy':
            self.comment_compression_ratio = 0.3
            self.min_lines_for_compression = 5
            self.duplicate_threshold = 2
            self.import_summary_threshold = 3
            self.max_lines_to_keep = 300
            self.max_class_methods_to_show = 2
            self.extremely_aggressive = True

        self.logger.info(f"Compression level set to {level}")

    def detect_language(self, file_path):
        """Detect programming language from file extension."""
        _, ext = os.path.splitext(file_path.lower())
        return self.language_extensions.get(ext, 'unknown')

    def compress_file_content(self, file_path, content):
        """Apply appropriate compression strategy based on file type."""
        line_count = len(content.splitlines())
        self.logger.info(f"Compressing {file_path} ({line_count} lines)")

        # Don't compress very small files unless extremely_aggressive is on
        if line_count < self.min_lines_for_compression and not self.extremely_aggressive:
            self.logger.info(f"Skipping small file: {file_path}")
            return content

        # Enforce max lines limit for any file
        if line_count > self.max_lines_to_keep:
            lines = content.splitlines()
            middle_marker = f"\n# ... {line_count - 2*self.max_lines_to_keep//3} more lines ...\n"
            content = "\n".join(lines[:self.max_lines_to_keep//3]) + \
                middle_marker + "\n".join(lines[-self.max_lines_to_keep//3:])
            self.logger.info(
                f"Truncated large file to {self.max_lines_to_keep//3*2} lines")
            line_count = self.max_lines_to_keep//3*2 + 1  # Update line count

        language = self.detect_language(file_path)

        # Skip test files in heavy compression mode
        if self.extremely_aggressive and ('test' in file_path.lower() or 'spec' in file_path.lower()):
            self.logger.info(
                f"Heavy compression: Summarizing test file {file_path}")
            return f"# Test file summary: {file_path}\n# {line_count} lines of testing code\n# Skipped in heavy compression mode"

        # Use language-specific handler if available
        if language in self.language_handlers:
            before_size = len(content)
            compressed = self.language_handlers[language](content)
            after_size = len(compressed)
            self.logger.info(
                f"Compressed {file_path} from {before_size} to {after_size} bytes ({after_size/before_size*100:.1f}%)")
            return compressed

        # Generic compression for other languages
        before_size = len(content)
        compressed = self.generic_compression(content)
        after_size = len(compressed)
        self.logger.info(
            f"Generic compression of {file_path} from {before_size} to {after_size} bytes ({after_size/before_size*100:.1f}%)")
        return compressed

    def generic_compression(self, content):
        """Generic compression strategies that work across languages."""
        # Compress multi-line comments
        content = self.compress_multiline_comments(content)

        # Compress single-line comments
        content = self.compress_single_line_comments(content)

        # Compress blank lines (keep structure but reduce multiples)
        content = self.blank_line_pattern.sub('\n\n', content)

        # Remove trailing whitespace
        content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)

        # In extremely aggressive mode, further compress whitespace
        if self.extremely_aggressive:
            # Replace multiple spaces with single space (except in indentation)
            content = re.sub(r'(?<=\S)[ \t]{2,}(?=\S)', ' ', content)

            # Truncate very long lines
            content = self.truncate_long_lines(content, 100)

        return content

    def truncate_long_lines(self, content, max_length=100):
        """Truncate very long lines to save tokens."""
        lines = content.splitlines()
        result = []

        for line in lines:
            if len(line) > max_length + 20:  # Only truncate significantly long lines
                # Preserve indentation
                indent = re.match(r'^(\s*)', line).group(1)
                truncated = line[:max_length] + '...'
                result.append(truncated)
            else:
                result.append(line)

        return '\n'.join(result)

    def compress_python(self, content):
        """Python-specific compression."""
        self.logger.info("Applying Python-specific compression")

        # Apply general compression techniques first
        content = self.generic_compression(content)

        # First try to parse with ast to do intelligent compression
        try:
            tree = ast.parse(content)

            # Summarize imports if there are many
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for name in node.names:
                        if isinstance(node, ast.ImportFrom) and node.module:
                            imports.append(
                                f"from {node.module} import {name.name}")
                        else:
                            imports.append(f"import {name.name}")

            if len(imports) > self.import_summary_threshold:
                # Replace imports with summary
                import_modules = sorted(
                    set([name.split()[-1].split('.')[0] for name in imports]))
                imports_summary = f"# Imports summary: {', '.join(import_modules)}"
                content = re.sub(
                    r'(?:^import.*$|^from.*import.*$)[\n\r]*', '', content, flags=re.MULTILINE)
                content = imports_summary + "\n\n" + content.lstrip()
                self.logger.info(
                    f"Summarized {len(imports)} imports into {len(import_modules)} modules")

            # Identify and summarize utility/helper functions
            functions = {}
            classes = {}

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions[node.name] = ast.get_source_segment(
                        content, node)
                elif isinstance(node, ast.ClassDef):
                    classes[node.name] = {
                        'methods': [],
                        'source': ast.get_source_segment(content, node)
                    }
                    for subnode in ast.walk(node):
                        if isinstance(subnode, ast.FunctionDef):
                            classes[node.name]['methods'].append(subnode.name)

            # Only in heavy mode, aggressively compress utility functions
            if self.extremely_aggressive:
                # Identify and compress non-public utility functions (starting with _)
                for name, source in functions.items():
                    if name.startswith('_') and not name.startswith('__') and len(source.splitlines()) > 5:
                        placeholder = f"def {name}(...):  # Utility function: {len(source.splitlines())} lines"
                        content = content.replace(source, placeholder)
                        self.logger.info(
                            f"Compressed utility function {name} ({len(source.splitlines())} lines)")

            # Compress large classes with many methods
            for name, data in classes.items():
                methods = data['methods']
                source_lines = data['source'].splitlines()

                # Different thresholds based on compression level
                if len(methods) > self.max_class_methods_to_show and len(source_lines) > 30:
                    # Extract class signature and first few lines
                    class_def_line = next((i for i, line in enumerate(
                        source_lines) if line.strip().startswith('class')), 0)
                    docstring_end = class_def_line + 1

                    # Find where docstring ends if there is one
                    if len(source_lines) > class_def_line + 1 and re.match(r'\s+[\'"]', source_lines[class_def_line + 1]):
                        for i in range(class_def_line + 1, len(source_lines)):
                            if re.search(r'[\'"]$', source_lines[i]):
                                docstring_end = i + 1
                                break

                    # Show important methods (init and a few others)
                    important_methods = [
                        '__init__'] + [m for m in methods if not m.startswith('_')][:self.max_class_methods_to_show]
                    methods_summary = ', '.join(important_methods)
                    additional_methods = len(methods) - len(important_methods)

                    # Create compressed representation
                    class_summary = "\n".join(
                        source_lines[:docstring_end]) + "\n"
                    class_summary += f"    # Key methods: {methods_summary}\n"
                    if additional_methods > 0:
                        class_summary += f"    # + {additional_methods} more methods\n"
                    class_summary += f"    # Total: {len(source_lines)} lines\n"
                    class_summary += "    # ..."

                    # Replace the class definition
                    content = content.replace(data['source'], class_summary)
                    self.logger.info(
                        f"Compressed class {name} with {len(methods)} methods")

        except SyntaxError as e:
            self.logger.warning(f"AST parsing failed: {e}")
            # If AST parsing fails, fall back to regex-based compression
            pass

        # Additional Python-specific compressions

        # Compress long list literals
        content = re.sub(r'\[\s*([^]]{50,}?)\s*\]',
                         r'[...]  # List with elements', content)

        # Compress long dict literals
        content = re.sub(r'\{\s*([^}]{50,}?)\s*\}',
                         r'{...}  # Dict with key-values', content)

        # Compress long comprehensions
        content = re.sub(r'\[[^]]{50,}? for [^]]+\]',
                         r'[... for ... in ...]  # List comprehension', content)

        return content

    def compress_javascript(self, content):
        """JavaScript/TypeScript compression."""
        self.logger.info("Applying JavaScript-specific compression")

        # Apply generic compression first
        content = self.generic_compression(content)

        # Summarize imports
        import_statements = re.findall(
            r'^(?:import|export).*?;?\s*$', content, re.MULTILINE)
        if len(import_statements) > self.import_summary_threshold:
            imports_joined = '\n'.join(import_statements)
            imported_modules = re.findall(
                r'from\s+[\'"](.+?)[\'"]', imports_joined)
            imported_modules += re.findall(
                r'import\s+[^{]*?[\'"](.+?)[\'"]', imports_joined)

            # Get unique module names, removing paths
            unique_modules = sorted(
                set([m.split('/').pop() for m in imported_modules]))

            imports_summary = f"// Imports summary: {', '.join(unique_modules)}"
            for stmt in import_statements:
                content = content.replace(stmt, '')
            content = imports_summary + "\n\n" + content.lstrip()
            self.logger.info(f"Summarized {len(import_statements)} imports")

        # Compress object literals
        content = re.sub(r'\{\s*([^{]*?\n){5,}[^}]*?\}',
                         r'{ /* Large object literal */ }', content)

        # Compress JSX in extremely aggressive mode
        if self.extremely_aggressive:
            # Simplify JSX components (only in heavy mode)
            content = re.sub(r'<([A-Z][a-zA-Z0-9]*)([^>]{50,}?)>[\s\S]{100,}?</\1>',
                             r'<\1 /* props */ >/* complex component content */</\1>', content)
            self.logger.info("Applied JSX compression")

        return content

    def compress_json(self, content):
        """Intelligently compress JSON content."""
        self.logger.info("Applying JSON-specific compression")

        try:
            # First try to parse the JSON
            data = json.loads(content)

            # Handle large arrays
            if isinstance(data, list):
                if len(data) > 10:
                    sample_items = data[:3]
                    return f"// JSON array with {len(data)} items. First 3 items:\n" + json.dumps(sample_items, indent=2)
                elif len(data) > 3 and self.extremely_aggressive:
                    # In heavy mode, be more aggressive
                    sample_items = data[0]
                    return f"// JSON array with {len(data)} items. First item:\n" + json.dumps(sample_items, indent=2)

            # Handle large objects with repetitive structure
            if isinstance(data, dict):
                if len(data) > 20:
                    sample_keys = list(data.keys())[:5]
                    sample_data = {k: data[k] for k in sample_keys}
                    return f"// JSON object with {len(data)} keys. Sample keys: {', '.join(sample_keys[:10])}...\n" + json.dumps(sample_data, indent=2)
                elif len(data) > 5 and self.extremely_aggressive:
                    # In heavy mode, be more aggressive
                    sample_keys = list(data.keys())[:3]
                    sample_data = {k: data[k] for k in sample_keys}
                    return f"// JSON object with {len(data)} keys. Sample keys: {', '.join(sample_keys)}...\n" + json.dumps(sample_data, indent=2)

            # If small enough to keep, but still could use beautification
            if len(content) < 1000:
                return json.dumps(data, indent=2)

            return content

        except json.JSONDecodeError:
            self.logger.warning("JSON parsing failed")
            return content  # If not valid JSON, return as is

    def compress_html(self, content):
        """Intelligently compress HTML."""
        self.logger.info("Applying HTML-specific compression")

        # Remove HTML comments
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)

        # Compress multiple spaces in tags
        content = re.sub(r'>\s+<', '>\n<', content)

        # In heavy mode, simplify large repeated sections
        if self.extremely_aggressive:
            # Identify repeating elements (like list items, table rows)
            list_items = re.findall(r'(<li\b[^>]*>[\s\S]*?</li>)', content)
            if len(list_items) > 5:
                # Replace all but first 2 list items
                list_pattern = r'(<li\b[^>]*>[\s\S]*?</li>)(\s*<li\b[^>]*>[\s\S]*?</li>)' + \
                    r'(\s*<li\b[^>]*>[\s\S]*?</li>){3,}'
                replacement = r'\1\2\n<!-- ... and ' + \
                    str(len(list_items) - 2) + ' more list items ... -->'
                content = re.sub(list_pattern, replacement, content)
                self.logger.info(f"Compressed {len(list_items)} list items")

            # Similarly for table rows
            table_rows = re.findall(r'(<tr\b[^>]*>[\s\S]*?</tr>)', content)
            if len(table_rows) > 5:
                # Replace all but first 2 rows
                row_pattern = r'(<tr\b[^>]*>[\s\S]*?</tr>)(\s*<tr\b[^>]*>[\s\S]*?</tr>)' + \
                    r'(\s*<tr\b[^>]*>[\s\S]*?</tr>){3,}'
                replacement = r'\1\2\n<!-- ... and ' + \
                    str(len(table_rows) - 2) + ' more table rows ... -->'
                content = re.sub(row_pattern, replacement, content)
                self.logger.info(f"Compressed {len(table_rows)} table rows")

        return content

    def compress_css(self, content):
        """Intelligently compress CSS."""
        self.logger.info("Applying CSS-specific compression")

        # Remove CSS comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

        # Identify vendor prefixes and consolidate
        vendor_prefixed = re.findall(r'(-webkit-|-moz-|-ms-|-o-).*?;', content)
        if len(vendor_prefixed) > 5:
            content = re.sub(
                r'^\s*(?:-webkit-|-moz-|-ms-|-o-).*?;\s*$', '', content, flags=re.MULTILINE)
            content = "/* Note: Vendor prefixes consolidated */\n" + content
            self.logger.info(
                f"Consolidated {len(vendor_prefixed)} vendor prefixes")

        # In heavy mode, compress repeated property patterns
        if self.extremely_aggressive:
            # Find selectors with many properties
            selectors = re.findall(r'([^\{\}]+)\s*\{([^\{\}]+)\}', content)
            long_rules = [rule for selector,
                          rule in selectors if rule.count(';') > 8]

            for rule in long_rules:
                # Create a summarized version
                prop_count = rule.count(';')
                summarized = rule.split(';')[:4]
                summarized = ';'.join(
                    summarized) + f'; /* ... {prop_count - 4} more properties ... */'

                # Replace in the content
                content = content.replace(rule, summarized)
                self.logger.info(
                    f"Compressed CSS rule with {prop_count} properties")

        return content

    def compress_markdown(self, content):
        """Compress markdown content."""
        self.logger.info("Applying Markdown-specific compression")

        # In heavy mode, compress long markdown files substantially
        if self.extremely_aggressive:
            lines = content.splitlines()

            if len(lines) > 50:
                # Keep headings and a few lines after each heading
                result = []
                in_heading_section = False
                lines_after_heading = 0

                for line in lines:
                    if re.match(r'^#{1,6}\s', line):  # It's a heading
                        result.append(line)
                        in_heading_section = True
                        lines_after_heading = 0
                    elif in_heading_section and lines_after_heading < 3:
                        result.append(line)
                        lines_after_heading += 1
                    elif in_heading_section and lines_after_heading >= 3:
                        if result[-1] != "...":
                            result.append("...")
                        in_heading_section = False

                # If we compressed significantly, return
                if len(result) < len(lines) * 0.6:
                    self.logger.info(
                        f"Compressed markdown from {len(lines)} to {len(result)} lines")
                    return "\n".join(result)

        # Apply generic compression for other cases
        return self.generic_compression(content)

    def compress_multiline_comments(self, content):
        """Compress multiline comments/docstrings."""
        self.logger.info("Compressing multiline comments/docstrings")

        def replace_docstring(match):
            docstring = match.group(0)
            lines = docstring.splitlines()

            # Keep short docstrings as is
            if len(lines) <= 3:
                return docstring

            # For longer docstrings, keep first line, compress middle, keep last
            first_line = lines[0]
            last_line = lines[-1]

            # Extract key information to preserve
            params = re.findall(
                r'@param|@arg|\:param|\:arg|Parameters:', docstring)
            returns = re.findall(r'@return|\:return|Returns:', docstring)
            examples = re.findall(r'@example|Example:|Examples:', docstring)

            # Build a summary of what's in the docstring
            summary = []
            if params:
                summary.append(f"{len(params)} params")
            if returns:
                summary.append("return info")
            if examples:
                summary.append("examples")

            # Extremely aggressive mode - even more compression
            if self.extremely_aggressive:
                return f"{first_line}\n# Compressed {len(lines)} line docstring\n{last_line}"

            # Regular compression with content summary
            if summary:
                return f"{first_line}\n# Compressed docstring ({', '.join(summary)})\n{last_line}"
            else:
                return f"{first_line}\n# Compressed docstring ({len(lines)} lines)\n{last_line}"

        return self.docstring_pattern.sub(replace_docstring, content)

    def compress_single_line_comments(self, content):
        """Intelligently compress single-line comments."""
        self.logger.info("Compressing single-line comments")

        lines = content.splitlines()
        result_lines = []
        comment_block = []

        for line in lines:
            if re.match(self.comment_pattern, line):
                comment_block.append(line)
            else:
                # Process any accumulated comment block
                if comment_block:
                    if len(comment_block) > 3:
                        # In extremely aggressive mode, compress more
                        if self.extremely_aggressive and len(comment_block) > 5:
                            result_lines.append(comment_block[0])
                            result_lines.append(
                                f"# ... {len(comment_block)-1} more comment lines ...")
                        else:
                            # Regular compression - keep first, last, and a summary
                            result_lines.append(comment_block[0])
                            result_lines.append(
                                f"# ... {len(comment_block)-2} more comment lines ...")
                            result_lines.append(comment_block[-1])
                    else:
                        # Keep short comment blocks
                        result_lines.extend(comment_block)
                    comment_block = []
                result_lines.append(line)

        # Handle any remaining comment block
        if comment_block:
            if len(comment_block) > 3:
                if self.extremely_aggressive and len(comment_block) > 5:
                    result_lines.append(comment_block[0])
                    result_lines.append(
                        f"# ... {len(comment_block)-1} more comment lines ...")
                else:
                    result_lines.append(comment_block[0])
                    result_lines.append(
                        f"# ... {len(comment_block)-2} more comment lines ...")
                    result_lines.append(comment_block[-1])
            else:
                result_lines.extend(comment_block)

        return '\n'.join(result_lines)

    def analyze_file_importance(self, file_path, repo_stats):
        """
        Determine the importance of a file in the codebase.
        Returns a score from 0-10 where 10 is most important.
        """
        _, filename = os.path.split(file_path)
        _, ext = os.path.splitext(filename.lower())

        # Special files
        if filename.lower() in ('main.py', 'app.py', 'index.js', 'server.js', 'app.js'):
            return 10

        # Important by extension for core languages
        if ext in ('.py', '.js', '.ts', '.jsx', '.tsx'):
            return 8

        # Config files are important but slightly less
        if filename.endswith(('config.js', 'config.py', 'settings.py')):
            return 7

        # Importation frequency
        import_count = repo_stats.get('imports', {}).get(file_path, 0)
        if import_count > 5:
            return 7

        # Test files are less important
        if 'test' in filename or 'spec' in filename:
            return 3

        # Default
        return 5

    def find_duplicate_code(self, all_content):
        """Identify duplicated code sections across files."""
        self.logger.info("Finding duplicate code sections")

        # Extract chunks by splitting on common delimiters
        chunks = []
        for file_path, content in all_content.items():
            lines = content.splitlines()
            current_chunk = []

            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith(('#', '//', '/*', '*')):
                    if current_chunk:
                        chunk_text = '\n'.join(current_chunk)
                        if len(chunk_text) > 50:  # Only consider substantial chunks
                            chunks.append((file_path, chunk_text))
                        current_chunk = []
                else:
                    current_chunk.append(line)

            # Add any remaining chunk
            if current_chunk:
                chunk_text = '\n'.join(current_chunk)
                if len(chunk_text) > 50:
                    chunks.append((file_path, chunk_text))

        # Hash chunks to find duplicates
        chunk_hashes = {}
        duplicates = {}

        for file_path, chunk in chunks:
            chunk_hash = hashlib.md5(chunk.encode()).hexdigest()

            if chunk_hash in chunk_hashes:
                if chunk_hash not in duplicates:
                    duplicates[chunk_hash] = {
                        'content': chunk,
                        'files': [chunk_hashes[chunk_hash]]
                    }
                duplicates[chunk_hash]['files'].append(file_path)
            else:
                chunk_hashes[chunk_hash] = file_path

        self.logger.info(
            f"Found {len(duplicates)} potential duplicate code sections")
        return duplicates

    def analyze_repository(self, all_content):
        """Analyze repository for code metrics and statistics."""
        self.logger.info("Analyzing repository structure")

        stats = {
            'imports': {},      # file -> import count
            'file_size': {},    # file -> line count
            'importance': {},   # file -> importance score
            'duplicates': None,  # duplicate code sections
            'languages': {},    # language -> count
            'largest_files': []  # list of largest files
        }

        # Calculate basic metrics
        for file_path, content in all_content.items():
            line_count = len(content.splitlines())
            stats['file_size'][file_path] = line_count

            # Track languages
            language = self.detect_language(file_path)
            stats['languages'][language] = stats['languages'].get(
                language, 0) + 1

            # Track largest files
            stats['largest_files'].append((file_path, line_count))

            # Count imports of this file
            file_name = os.path.basename(file_path)
            name_no_ext = os.path.splitext(file_name)[0]

            for other_path, other_content in all_content.items():
                if other_path != file_path:
                    # Count imports in Python
                    if 'import ' + name_no_ext in other_content or 'from ' + name_no_ext in other_content:
                        stats['imports'][file_path] = stats['imports'].get(
                            file_path, 0) + 1
                    # Count imports in JS
                    if "import " in other_content and "from '" + name_no_ext in other_content:
                        stats['imports'][file_path] = stats['imports'].get(
                            file_path, 0) + 1

        # Sort largest files
        stats['largest_files'] = sorted(
            stats['largest_files'], key=lambda x: x[1], reverse=True)[:10]

        # Calculate importance scores
        for file_path in all_content:
            stats['importance'][file_path] = self.analyze_file_importance(
                file_path, stats)

        # Find duplicate code
        stats['duplicates'] = self.find_duplicate_code(all_content)

        return stats

    def generate_repository_summary(self, repo_stats, all_content):
        """Generate a natural language summary of the repository."""
        self.logger.info("Generating repository summary")

        summary = []

        # Size metrics
        total_files = len(all_content)
        total_lines = sum(repo_stats['file_size'].values())
        summary.append(
            f"Repository contains {total_files} files with approximately {total_lines} lines of code.")

        # Language breakdown
        langs = repo_stats['languages']
        if langs:
            lang_counts = sorted([(l, c) for l, c in langs.items() if l != 'unknown'],
                                 key=lambda x: x[1], reverse=True)
            if lang_counts:
                lang_summary = ", ".join(
                    [f"{lang} ({count})" for lang, count in lang_counts[:3]])
                if len(lang_counts) > 3:
                    lang_summary += f", and {len(lang_counts) - 3} other languages"
                summary.append(f"Main languages: {lang_summary}.")

        # Largest files
        if repo_stats['largest_files']:
            largest = repo_stats['largest_files'][0]
            summary.append(f"Largest file: {largest[0]} ({largest[1]} lines).")

        # Most important files
        important_files = sorted(
            [(f, s) for f, s in repo_stats['importance'].items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]

        if important_files:
            summary.append("Key files include:")
            for file_path, score in important_files:
                summary.append(f"- {file_path}")

        # Duplicate code sections
        if repo_stats['duplicates']:
            dup_count = len(repo_stats['duplicates'])
            total_dup_lines = sum(len(d['content'].splitlines())
                                  for d in repo_stats['duplicates'].values())

            if dup_count > 0:
                summary.append(
                    f"Found {dup_count} duplicated code sections ({total_dup_lines} lines). Repetitive patterns have been compressed.")

        # Note about compression level
        if self.extremely_aggressive:
            summary.append(
                "Note: Heavy compression applied - focusing on structure and key elements while aggressively summarizing details.")

        return "\n".join(summary)

    def compress_repository(self, all_content):
        """Apply intelligent compression to an entire repository."""
        self.logger.info("Starting repository compression")

        # First analyze the repository
        repo_stats = self.analyze_repository(all_content)

        # Generate repository summary
        repo_summary = self.generate_repository_summary(
            repo_stats, all_content)

        # In extremely aggressive mode, limit to top important files
        if self.extremely_aggressive and len(all_content) > 20:
            # Sort files by importance
            files_by_importance = sorted(
                [(f, repo_stats['importance'].get(f, 0))
                 for f in all_content.keys()],
                key=lambda x: x[1],
                reverse=True
            )

            # Keep only the top files
            top_files = [f for f, _ in files_by_importance[:15]]
            skipped_files = [
                f for f in all_content.keys() if f not in top_files]

            # Create a summary for skipped files
            if skipped_files:
                all_content['_SKIPPED_FILES_SUMMARY.txt'] = f"# Skipped {len(skipped_files)} less important files in heavy compression mode\n\n" + \
                    "# Files skipped:\n" + \
                    "\n".join(
                    [f"# - {f}" for f in skipped_files])

                # Remove skipped files
                for f in skipped_files:
                    all_content.pop(f)

                self.logger.info(
                    f"Heavy compression: Skipped {len(skipped_files)} less important files")

        # Compress each file based on importance
        compressed_content = {}
        for file_path, content in all_content.items():
            importance = repo_stats['importance'].get(file_path, 5)

            if importance >= 8:
                # High importance: standard compression
                compressed_content[file_path] = self.compress_file_content(
                    file_path, content)
            elif importance >= 5:
                # Medium importance: more aggressive compression
                if self.extremely_aggressive:
                    # For heavy compression, be more aggressive with medium importance files
                    content = self.add_compression_header(file_path, content)
                compressed_content[file_path] = self.compress_file_content(
                    file_path, content)
            else:
                # Low importance: most aggressive compression or summary
                if len(content.splitlines()) > 30 and self.extremely_aggressive:
                    language = self.detect_language(file_path)
                    compressed_content[file_path] = f"# File summary: {file_path} ({len(content.splitlines())} lines, {language})\n# This file was compressed due to lower relevance.\n\n# First few lines:\n" + \
                        "\n".join(content.splitlines()[:10]) + "\n\n# ..."
                    self.logger.info(
                        f"Created summary for low importance file {file_path}")
                else:
                    compressed_content[file_path] = self.compress_file_content(
                        file_path, content)

        # Handle duplicates
        if repo_stats['duplicates']:
            for dup_hash, dup_info in repo_stats['duplicates'].items():
                if len(dup_info['files']) >= self.duplicate_threshold:
                    # Replace duplicate content with reference
                    for file_path in dup_info['files'][1:]:
                        if file_path in compressed_content:
                            compressed = compressed_content[file_path]
                            chunk = dup_info['content']
                            if chunk in compressed:
                                replacement = f"# DUPLICATE CODE: Same as in {dup_info['files'][0]}\n# {len(chunk.splitlines())} lines\n"
                                compressed_content[file_path] = compressed.replace(
                                    chunk, replacement)
                                self.logger.info(
                                    f"Replaced duplicate code in {file_path} with reference")

        return repo_summary, compressed_content

    def add_compression_header(self, file_path, content):
        """Add a header to indicate this file is compressed."""
        return f"# Note: This file has been compressed for LLM analysis\n# Original file: {file_path}\n\n{content}"


# Function to compress an analysis file
def compress_analysis_output(output_filename, compression_level='medium'):
    """Compress an existing analysis file to be more LLM-friendly."""
    compressor = LLMFriendlyCompressor()

    # Set compression level
    compressor.set_compression_level(compression_level)

    # Read the existing file
    with open(output_filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into main sections
    readme_section = ""
    structure_section = ""
    file_contents_section = ""

    # Split the content into the three main sections
    if "README:" in content:
        readme_and_rest = content.split("Structure:", 1)
        readme_section = readme_and_rest[0].strip()

        if len(readme_and_rest) > 1:
            structure_and_files = readme_and_rest[1].split("File Contents:", 1)
            structure_section = "Structure:" + structure_and_files[0].strip()

            if len(structure_and_files) > 1:
                file_contents_section = "File Contents:" + \
                    structure_and_files[1].strip()

    # Parse file content into a dictionary of files using regex for more reliable extraction
    files_content = {}
    if file_contents_section:
        # Use regex to find all file blocks
        file_pattern = r'File: (.*?)(?:\r?\n)Content:(?:\r?\n)?([\s\S]*?)(?=(?:\r?\n){2}File: |$)'
        matches = re.finditer(file_pattern, file_contents_section)

        for match in matches:
            file_path = match.group(1).strip()
            file_content = match.group(2).strip()
            files_content[file_path] = file_content

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

    # Write the compressed output
    compressed_filename = output_filename.replace(
        '.txt', f'_compressed_{compression_level}.txt')
    with open(compressed_filename, 'w', encoding='utf-8') as f:
        f.write(compressed_output)

    # Log stats about compression
    original_size = os.path.getsize(output_filename)
    compressed_size = os.path.getsize(compressed_filename)
    print(f"Original size: {original_size/1024:.1f} KB")
    print(f"Compressed size: {compressed_size/1024:.1f} KB")
    print(f"Compression ratio: {compressed_size/original_size*100:.1f}%")

    return compressed_filename


# Function to add to main.py
def add_compression_option(parser):
    """Add compression options to ArgumentParser."""
    parser.add_argument(
        "--compress",
        choices=['none', 'light', 'medium', 'heavy'],
        default='none',
        help="Compress output to be more LLM-friendly")
    parser.add_argument(
        "--compression-debug",
        action="store_true",
        help="Enable debug logging for compression")
