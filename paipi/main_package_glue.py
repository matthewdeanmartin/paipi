# --- new/updated imports at top of main.py ---
import io
import zipfile
from pathlib import Path
from typing import Dict

# NEW: import the generator bits


def _normalize_model(user_model: str | None) -> str:
    """
    Map friendly/legacy names to concrete API model ids used by Open Interpreter.
    Defaults to a solid general model if unknown.
    """
    if not user_model:
        return "gpt-4o-mini"  # default: fast/cheap/good

    m = user_model.strip().lower().replace("_", "-")

    MODEL_MAP: Dict[str, str] = {
        # OpenAI "frontier"
        "gpt-5": "gpt-5",  # if enabled for your key
        "gpt-4.1": "gpt-4.1",
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "o4-mini": "o4-mini",
        "o3-mini": "o3-mini",
        "o3-mini-high": "o3-mini-high",
        # Common aliases
        "gpt-4": "gpt-4o",  # alias to a modern 4o
        "gpt4": "gpt-4o",
        "gpt-4-turbo": "gpt-4o",
        # If someone passes vendor-y names, keep a best-effort default
        "claude-3.5-sonnet": "gpt-4o",
        "gemini-2.0-flash": "gpt-4o-mini",
        "mixtral-8x7b": "gpt-4o-mini",
    }
    return MODEL_MAP.get(m, "gpt-4o-mini")


def _zip_dir_to_bytes(dir_path: Path) -> bytes:
    """
    Zip a directory into memory and return raw bytes.
    """
    with io.BytesIO() as buf:
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in dir_path.rglob("*"):
                if p.is_file():
                    zf.write(p, arcname=str(p.relative_to(dir_path)))
        return buf.getvalue()
