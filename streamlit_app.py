import sys
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from llm_evaluation_console.app import *  # noqa: E402,F403
