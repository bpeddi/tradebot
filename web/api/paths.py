import os
import platform
import sys


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def bot_python_executable():
    """Prefer the project's own venv interpreter (so trading_bot.py's
    dependencies are available) over sys.executable, which on Windows venvs
    can report the base interpreter rather than the venv's own python.exe."""
    root = repo_root()
    if platform.system() == "Windows":
        candidate = os.path.join(root, ".venv", "Scripts", "python.exe")
    else:
        candidate = os.path.join(root, ".venv", "bin", "python")
    return candidate if os.path.exists(candidate) else sys.executable
