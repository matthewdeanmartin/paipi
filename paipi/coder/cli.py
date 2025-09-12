from __future__ import annotations
import argparse

import os
import sys
from pathlib import Path

from paipi.coder.generate_package import GenerationConfig, DockerOpenInterpreter, LibrarySpec


def main() -> None:
    """Example usage of the DockerOpenInterpreter"""

    parser = argparse.ArgumentParser(
        description="Generate Python libraries using Open Interpreter in Docker"
    )
    parser.add_argument("--name", required=True, help="Library name")
    parser.add_argument("--description", required=True, help="PyPI description")
    parser.add_argument(
        "--readme", required=True, help="Path to README file or inline content"
    )
    parser.add_argument(
        "--python-version", default="3.11", help="Python version (default: 3.11)"
    )
    parser.add_argument("--cache-folder", default="./cache", help="Cache folder path")
    parser.add_argument("--openai-api-key", help="OpenAI API key")
    parser.add_argument(
        "--model", default="gpt-4", help="Model to use (default: gpt-4)"
    )
    parser.add_argument("--timeout", type=int, default=3600, help="Timeout in seconds")
    parser.add_argument("--list", action="store_true", help="List generated libraries")
    parser.add_argument("--cleanup", type=int, help="Remove cache older than N days")

    args = parser.parse_args()

    config = GenerationConfig(
        python_version=args.python_version,
        cache_folder=args.cache_folder,
        timeout_seconds=args.timeout,
        openai_api_key=args.openai_api_key or os.environ.get("OPENAI_API_KEY"),
        model=args.model,
    )

    interpreter = DockerOpenInterpreter(config)

    if args.list:
        libraries = interpreter.list_generated_libraries()
        if libraries:
            print("Generated libraries:")
            for lib in libraries:
                print(f"  - {lib['library_name']} ({lib['generation_timestamp']})")
                print(f"    Path: {lib['output_path']}")
        else:
            print("No generated libraries found.")
        return

    if args.cleanup is not None:
        removed = interpreter.cleanup_cache(args.cleanup)
        print(f"Removed {removed} old cache directories.")
        return

    # Read README content
    readme_content = args.readme
    if Path(args.readme).exists():
        readme_content = Path(args.readme).read_text(encoding="utf-8")

    python_version = args.python_version
    # Create library specification
    spec = LibrarySpec(
        name=args.name,
        pypi_description=args.description,
        readme_content=readme_content,
        python_version=python_version,
    )

    try:
        result = interpreter.generate_library(spec)
        print("✅ Library generated successfully!")
        print(f"📁 Output directory: {result['output_directory']}")
        print(f"📋 Log file: {result['log_file']}")
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()