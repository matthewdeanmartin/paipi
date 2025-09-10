#!/usr/bin/env python3
"""
Docker Open Interpreter Module

A self-contained module for running Open Interpreter in a Docker container
to generate Python libraries based on PyPI descriptions and README specifications.
"""

import os
import sys
import json
import time
import shutil
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """Configuration for library generation"""
    python_version: str = "3.11"
    cache_folder: str = "./cache"
    container_name: Optional[str] = None
    timeout_seconds: int = 3600  # 1 hour default timeout
    openai_api_key: Optional[str] = None
    model: str = "gpt-4"
    max_retries: int = 3


@dataclass
class LibrarySpec:
    """Specification for the library to generate"""
    name: str
    pypi_description: str
    readme_content: str
    additional_requirements: List[str] = None

    def __post_init__(self):
        if self.additional_requirements is None:
            self.additional_requirements = []


class DockerOpenInterpreter:
    """
    A class to run Open Interpreter in Docker for generating Python libraries.
    """

    def __init__(self, config: GenerationConfig):
        self.config = config
        self.cache_path = Path(config.cache_folder).resolve()
        self.container_name = config.container_name or f"oi-generator-{int(time.time())}"

        # Ensure cache directory exists
        self.cache_path.mkdir(parents=True, exist_ok=True)

        # Setup logging for this instance
        self.logger = logging.getLogger(f"{__name__}.{self.container_name}")

        # Validate Docker installation
        self._validate_docker()

    def _validate_docker(self) -> None:
        """Validate that Docker is installed and running"""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            self.logger.info(f"Docker found: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("Docker is not installed or not running")

    def _create_dockerfile(self, work_dir: Path, python_version: str) -> None:
        """Create a Dockerfile for the Open Interpreter container"""
        dockerfile_content = f"""
FROM python:{python_version}-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    git \\
    curl \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Install Open Interpreter
RUN pip install --no-cache-dir open-interpreter

# Create output directory
RUN mkdir -p /output

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV OPENAI_API_KEY=""

# Default command
CMD ["python", "-c", "import interpreter; print('Open Interpreter ready')"]
"""

        dockerfile_path = work_dir / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content.strip())
        self.logger.info(f"Created Dockerfile at {dockerfile_path}")

    def _create_generation_script(self, work_dir: Path, spec: LibrarySpec) -> None:
        """Create the Python script that will run inside the container"""
        script_content = f'''
import os
import sys
import json
import traceback
from pathlib import Path
import interpreter

def main():
    """Main function to generate the Python library"""
    try:
        # Configure interpreter
        interpreter.auto_run = True
        interpreter.offline = False

        # Set API key if provided
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            interpreter.llm.api_key = api_key

        # Set model
        interpreter.llm.model = os.environ.get("MODEL", "gpt-4")

        # Library specification
        spec = {json.dumps(asdict(spec), indent=2)}

        print("="*50)
        print("STARTING LIBRARY GENERATION")
        print("="*50)
        print(f"Library: {{spec['name']}}")
        print(f"Python Version: {python_version}")
        print("="*50)

        # Create the generation prompt
        prompt = f"""
I need you to create a complete Python library called '{{spec['name']}}' based on the following specifications:

**PyPI Description:**
{{spec['pypi_description']}}

**README Content/Additional Requirements:**
{{spec['readme_content']}}

**Additional Requirements:**
{{', '.join(spec['additional_requirements']) if spec['additional_requirements'] else 'None'}}

Please create a complete, production-ready Python library with the following structure:
1. Proper package structure with __init__.py files
2. Core implementation modules
3. setup.py or pyproject.toml for packaging
4. README.md file
5. requirements.txt if needed
6. Basic tests in a tests/ directory
7. Proper documentation and docstrings

Make sure to:
- Follow Python best practices and PEP 8
- Include proper error handling
- Add type hints where appropriate
- Create meaningful examples in the README
- Ensure the code is well-documented

Save everything in the /output directory with the proper package structure.
Start by creating the directory structure, then implement each module step by step.
"""

        print("Sending prompt to Open Interpreter...")
        print("-" * 30)

        # Run the generation
        response = interpreter.chat(prompt)

        print("-" * 30)
        print("Generation completed!")

        # Create a generation summary
        summary = {{
            "library_name": spec['name'],
            "generation_timestamp": str(datetime.now()),
            "python_version": "{python_version}",
            "status": "completed",
            "output_directory": "/output"
        }}

        with open("/output/generation_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        print("Summary saved to generation_summary.json")

        # List generated files
        output_path = Path("/output")
        if output_path.exists():
            print("\\nGenerated files:")
            for file_path in output_path.rglob("*"):
                if file_path.is_file():
                    print(f"  {{file_path.relative_to(output_path)}}")

    except Exception as e:
        error_info = {{
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": str(datetime.now())
        }}

        print(f"ERROR: {{e}}")
        print(f"TRACEBACK:\\n{{traceback.format_exc()}}")

        # Save error info
        try:
            with open("/output/error_log.json", "w") as f:
                json.dump(error_info, f, indent=2)
        except:
            pass

        sys.exit(1)

if __name__ == "__main__":
    main()
'''

        script_path = work_dir / "generate_library.py"
        script_path.write_text(script_content)
        self.logger.info(f"Created generation script at {script_path}")

    def _build_container(self, work_dir: Path) -> None:
        """Build the Docker container"""
        self.logger.info(f"Building Docker container: {self.container_name}")

        build_cmd = [
            "docker", "build",
            "-t", self.container_name,
            str(work_dir)
        ]

        try:
            result = subprocess.run(
                build_cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                check=True
            )
            self.logger.info("Container built successfully")
            if result.stdout:
                self.logger.debug(f"Build output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to build container: {e.stderr}")
            raise RuntimeError(f"Docker build failed: {e.stderr}")

    def _run_container(self, work_dir: Path) -> Dict[str, Any]:
        """Run the container and capture output"""
        output_dir = self.cache_path / f"output_{int(time.time())}"
        output_dir.mkdir(exist_ok=True)

        log_file = output_dir / "container.log"

        self.logger.info(f"Running container with output directory: {output_dir}")

        # Prepare environment variables
        env_vars = []
        if self.config.openai_api_key:
            env_vars.extend(["-e", f"OPENAI_API_KEY={self.config.openai_api_key}"])
        env_vars.extend(["-e", f"MODEL={self.config.model}"])

        run_cmd = [
                      "docker", "run",
                      "--rm",
                      "--name", f"{self.container_name}_run",
                      "-v", f"{output_dir}:/output",
                      "-v", f"{work_dir / 'generate_library.py'}:/workspace/generate_library.py",
                  ] + env_vars + [
                      self.container_name,
                      "python", "/workspace/generate_library.py"
                  ]

        try:
            self.logger.info("Starting container execution...")

            with open(log_file, 'w') as log_f:
                process = subprocess.Popen(
                    run_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )

                # Stream output in real-time
                for line in process.stdout:
                    print(f"[CONTAINER] {line.rstrip()}")
                    log_f.write(line)
                    log_f.flush()

                process.wait(timeout=self.config.timeout_seconds)

                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, run_cmd)

            self.logger.info("Container execution completed successfully")

            return {
                "status": "success",
                "output_directory": str(output_dir),
                "log_file": str(log_file)
            }

        except subprocess.TimeoutExpired:
            self.logger.error("Container execution timed out")
            try:
                subprocess.run(["docker", "kill", f"{self.container_name}_run"],
                               capture_output=True)
            except:
                pass
            raise RuntimeError(f"Container execution timed out after {self.config.timeout_seconds} seconds")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Container execution failed with exit code {e.returncode}")
            error_info = {"error": "Container execution failed", "exit_code": e.returncode}

            # Try to read error logs
            if log_file.exists():
                try:
                    error_info["logs"] = log_file.read_text()
                except:
                    pass

            raise RuntimeError(f"Container execution failed: {error_info}")

    def generate_library(self, spec: LibrarySpec) -> Dict[str, Any]:
        """
        Generate a Python library using Open Interpreter in Docker

        Args:
            spec: Library specification including name, description, and requirements

        Returns:
            Dict containing generation results and paths
        """
        self.logger.info(f"Starting library generation for: {spec.name}")

        # Create temporary working directory
        with tempfile.TemporaryDirectory() as temp_dir:
            work_dir = Path(temp_dir)

            try:
                # Create Dockerfile
                self._create_dockerfile(work_dir, self.config.python_version)

                # Create generation script
                self._create_generation_script(work_dir, spec)

                # Build container
                self._build_container(work_dir)

                # Run container
                result = self._run_container(work_dir)

                # Cleanup container image
                try:
                    subprocess.run(
                        ["docker", "rmi", self.container_name],
                        capture_output=True,
                        check=False
                    )
                except:
                    pass

                self.logger.info("Library generation completed successfully")
                return result

            except Exception as e:
                self.logger.error(f"Library generation failed: {e}")

                # Cleanup on failure
                try:
                    subprocess.run(
                        ["docker", "rmi", self.container_name],
                        capture_output=True,
                        check=False
                    )
                except:
                    pass

                raise

    def list_generated_libraries(self) -> List[Dict[str, Any]]:
        """List all generated libraries in the cache"""
        libraries = []

        for output_dir in self.cache_path.glob("output_*"):
            if output_dir.is_dir():
                summary_file = output_dir / "generation_summary.json"
                if summary_file.exists():
                    try:
                        with open(summary_file, 'r') as f:
                            summary = json.load(f)
                            summary['output_path'] = str(output_dir)
                            libraries.append(summary)
                    except:
                        pass

        return sorted(libraries, key=lambda x: x.get('generation_timestamp', ''))

    def cleanup_cache(self, older_than_days: int = 7) -> int:
        """Remove old generated libraries from cache"""
        cutoff_time = time.time() - (older_than_days * 24 * 3600)
        removed_count = 0

        for output_dir in self.cache_path.glob("output_*"):
            if output_dir.is_dir():
                try:
                    # Extract timestamp from directory name
                    timestamp = int(output_dir.name.split('_')[1])
                    if timestamp < cutoff_time:
                        shutil.rmtree(output_dir)
                        removed_count += 1
                        self.logger.info(f"Removed old cache directory: {output_dir}")
                except (ValueError, IndexError):
                    # Skip directories that don't match the expected naming pattern
                    pass

        return removed_count


def main():
    """Example usage of the DockerOpenInterpreter"""
    import argparse

    parser = argparse.ArgumentParser(description="Generate Python libraries using Open Interpreter in Docker")
    parser.add_argument("--name", required=True, help="Library name")
    parser.add_argument("--description", required=True, help="PyPI description")
    parser.add_argument("--readme", required=True, help="Path to README file or inline content")
    parser.add_argument("--python-version", default="3.11", help="Python version (default: 3.11)")
    parser.add_argument("--cache-folder", default="./cache", help="Cache folder path")
    parser.add_argument("--openai-api-key", help="OpenAI API key")
    parser.add_argument("--model", default="gpt-4", help="Model to use (default: gpt-4)")
    parser.add_argument("--timeout", type=int, default=3600, help="Timeout in seconds")
    parser.add_argument("--list", action="store_true", help="List generated libraries")
    parser.add_argument("--cleanup", type=int, help="Remove cache older than N days")

    args = parser.parse_args()

    config = GenerationConfig(
        python_version=args.python_version,
        cache_folder=args.cache_folder,
        timeout_seconds=args.timeout,
        openai_api_key=args.openai_api_key or os.environ.get("OPENAI_API_KEY"),
        model=args.model
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
        readme_content = Path(args.readme).read_text()

    # Create library specification
    spec = LibrarySpec(
        name=args.name,
        pypi_description=args.description,
        readme_content=readme_content
    )

    try:
        result = interpreter.generate_library(spec)
        print(f"✅ Library generated successfully!")
        print(f"📁 Output directory: {result['output_directory']}")
        print(f"📋 Log file: {result['log_file']}")
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()