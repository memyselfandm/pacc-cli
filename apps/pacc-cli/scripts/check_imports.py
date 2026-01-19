#!/usr/bin/env python3
"""Check that all imports in the package are satisfied by declared dependencies.

This script scans all Python files in the pacc/ directory, extracts import statements,
and verifies that third-party packages are declared in pyproject.toml dependencies.

Usage:
    python scripts/check_imports.py

Exit codes:
    0 - All imports are satisfied
    1 - Missing dependencies found
"""

import ast
import sys
from pathlib import Path
from typing import Set

# Standard library modules (Python 3.8+)
# This is comprehensive for Python 3.8-3.12
STDLIB_MODULES = {
    # Built-in types and functions
    "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio",
    "asyncore", "atexit", "audioop", "base64", "bdb", "binascii",
    "binhex", "bisect", "builtins", "bz2",
    # C
    "cProfile", "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd",
    "code", "codecs", "codeop", "collections", "colorsys", "compileall",
    "concurrent", "configparser", "contextlib", "contextvars", "copy",
    "copyreg", "crypt", "csv", "ctypes", "curses",
    # D
    "dataclasses", "datetime", "dbm", "decimal", "difflib", "dis",
    "distutils", "doctest",
    # E
    "email", "encodings", "enum", "errno",
    # F
    "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch",
    "fractions", "ftplib", "functools",
    # G
    "gc", "getopt", "getpass", "gettext", "glob", "graphlib", "grp", "gzip",
    # H
    "hashlib", "heapq", "hmac", "html", "http",
    # I
    "idlelib", "imaplib", "imghdr", "imp", "importlib", "inspect", "io",
    "ipaddress", "itertools",
    # J
    "json",
    # K
    "keyword",
    # L
    "lib2to3", "linecache", "locale", "logging", "lzma",
    # M
    "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
    "modulefinder", "msvcrt", "multiprocessing",
    # N
    "netrc", "nis", "nntplib", "numbers",
    # O
    "operator", "optparse", "os", "ossaudiodev",
    # P
    "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil",
    "platform", "plistlib", "poplib", "posix", "posixpath", "pprint",
    "profile", "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc",
    # Q
    "queue", "quopri",
    # R
    "random", "re", "readline", "reprlib", "resource", "rlcompleter",
    "runpy",
    # S
    "sched", "secrets", "select", "selectors", "shelve", "shlex",
    "shutil", "signal", "site", "smtpd", "smtplib", "sndhdr", "socket",
    "socketserver", "spwd", "sqlite3", "ssl", "stat", "statistics",
    "string", "stringprep", "struct", "subprocess", "sunau", "symtable",
    "sys", "sysconfig", "syslog",
    # T
    "tabnanny", "tarfile", "telnetlib", "tempfile", "termios", "test",
    "textwrap", "threading", "time", "timeit", "tkinter", "token",
    "tokenize", "tomllib", "trace", "traceback", "tracemalloc", "tty",
    "turtle", "turtledemo", "types", "typing", "typing_extensions",
    # U
    "unicodedata", "unittest", "urllib", "uu", "uuid",
    # V
    "venv",
    # W
    "warnings", "wave", "weakref", "webbrowser", "winreg", "winsound",
    "wsgiref",
    # X
    "xdrlib", "xml", "xmlrpc",
    # Z
    "zipapp", "zipfile", "zipimport", "zlib", "zoneinfo",
    # Private/internal
    "_thread", "__future__",
}

# Mapping from import names to PyPI package names (lowercase)
IMPORT_TO_PACKAGE = {
    "yaml": "pyyaml",
    "chardet": "chardet",
    "psutil": "psutil",
    "aiohttp": "aiohttp",
    "aiofiles": "aiofiles",
    "pytest": "pytest",
    "coverage": "coverage",
    "mypy": "mypy",
    "ruff": "ruff",
    "bandit": "bandit",
    "build": "build",
    "twine": "twine",
    "tomli": "tomli",
    "mkdocs": "mkdocs",
    "git": "gitpython",
    "PIL": "pillow",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
}


def get_imports_from_file(filepath: Path) -> Set[str]:
    """Extract all top-level import names from a Python file."""
    imports = set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(filepath))
    except SyntaxError:
        print(f"  Warning: Could not parse {filepath}")
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # Get just the top-level module
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                # Only absolute imports (level 0), not relative imports
                imports.add(node.module.split(".")[0])

    return imports


def get_declared_dependencies(pyproject_path: Path) -> Set[str]:
    """Extract declared dependencies from pyproject.toml."""
    dependencies = set()

    try:
        if sys.version_info >= (3, 11):
            import tomllib
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
        else:
            try:
                import tomli
                with open(pyproject_path, "rb") as f:
                    data = tomli.load(f)
            except ImportError:
                # Fallback: simple regex parsing
                import re
                content = pyproject_path.read_text()
                match = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
                if match:
                    deps_str = match.group(1)
                    for dep in re.findall(r'"([^"]+)"', deps_str):
                        pkg = re.split(r'[<>=!~\[]', dep)[0].strip()
                        dependencies.add(pkg.lower())
                return dependencies

        # Parse dependencies from pyproject.toml
        if "project" in data:
            for dep in data["project"].get("dependencies", []):
                pkg = dep.split("[")[0].split("<")[0].split(">")[0].split("=")[0].split("!")[0].split("~")[0].split(";")[0].strip()
                dependencies.add(pkg.lower())

            # Also check optional dependencies
            for group_deps in data["project"].get("optional-dependencies", {}).values():
                for dep in group_deps:
                    pkg = dep.split("[")[0].split("<")[0].split(">")[0].split("=")[0].split("!")[0].split("~")[0].split(";")[0].strip()
                    dependencies.add(pkg.lower())

    except Exception as e:
        print(f"  Warning: Could not parse pyproject.toml: {e}")

    return dependencies


def main():
    """Main function to check imports against dependencies."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    pacc_dir = project_root / "pacc"
    pyproject_path = project_root / "pyproject.toml"

    if not pacc_dir.exists():
        print(f"Error: pacc/ directory not found at {pacc_dir}")
        sys.exit(1)

    if not pyproject_path.exists():
        print(f"Error: pyproject.toml not found at {pyproject_path}")
        sys.exit(1)

    print("Checking imports against declared dependencies...")
    print(f"  Package directory: {pacc_dir}")
    print(f"  pyproject.toml: {pyproject_path}")
    print()

    # Get all imports from package
    all_imports: Set[str] = set()
    python_files = list(pacc_dir.rglob("*.py"))
    print(f"Scanning {len(python_files)} Python files...")

    for pyfile in python_files:
        imports = get_imports_from_file(pyfile)
        all_imports.update(imports)

    # Filter to third-party imports only
    third_party_imports = set()
    for imp in all_imports:
        # Skip standard library
        if imp in STDLIB_MODULES:
            continue
        # Skip internal package imports
        if imp == "pacc":
            continue
        third_party_imports.add(imp)

    print(f"Found {len(third_party_imports)} third-party imports: {sorted(third_party_imports)}")
    print()

    # Get declared dependencies
    declared_deps = get_declared_dependencies(pyproject_path)

    # Also add common mappings to declared (import name -> package name)
    declared_import_names = set()
    for pkg in declared_deps:
        declared_import_names.add(pkg)
        # Add reverse mappings
        for import_name, package_name in IMPORT_TO_PACKAGE.items():
            if package_name == pkg:
                declared_import_names.add(import_name)

    print(f"Declared dependencies: {sorted(declared_deps)}")
    print()

    # Check for missing dependencies
    missing = []
    for imp in sorted(third_party_imports):
        # Map import name to package name
        package_name = IMPORT_TO_PACKAGE.get(imp, imp).lower()
        if package_name not in declared_deps and imp.lower() not in declared_deps:
            missing.append((imp, package_name))

    if missing:
        print("❌ MISSING DEPENDENCIES:")
        for imp, pkg in missing:
            print(f"  - Import '{imp}' requires package '{pkg}'")
        print()
        print("Add these to pyproject.toml [project].dependencies")
        sys.exit(1)
    else:
        print("✅ All imports are satisfied by declared dependencies")
        sys.exit(0)


if __name__ == "__main__":
    main()
