"""
Docker Open Interpreter Module

A self-contained module for running Open Interpreter in a Docker container
to generate Python libraries based on PyPI descriptions and README specifications.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, StrictUndefined

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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
    python_version: str
    pypi_description: str
    readme_content: str
    additional_requirements: List[str] | None = None

    def __post_init__(self) -> None:
        if self.additional_requirements is None:
            self.additional_requirements = []


class DockerOpenInterpreter:
    """
    A class to run Open Interpreter in Docker for generating Python libraries.
    """

    def __init__(self, config: GenerationConfig):
        self.config = config
        self.cache_path = Path(config.cache_folder).resolve()
        self.container_name = (
            config.container_name or f"oi-generator-{int(time.time())}"
        )

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
                ["docker", "--version"], capture_output=True, text=True, check=True
            )
            self.logger.info(f"Docker found: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError) as some_error:
            raise RuntimeError("Docker is not installed or not running") from some_error

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

    def _create_generation_script(self, work_dir: Path, spec: LibrarySpec) -> Path:
        """
        Render generate_library.py from the Jinja2 template generate_library.py.j2
        and write it to the working directory so the container can execute it.

        Returns:
            Path to the rendered script.
        """
        # Where to look for the template:
        # 1) a local "templates" folder next to this module
        # 2) this module's folder (if you keep the .j2 next to the file)
        # 3) current working directory as a final fallback
        module_dir = Path(__file__).parent.resolve()
        search_paths = [
            module_dir / "templates",
            module_dir,
            Path.cwd(),
        ]

        env = Environment(
            loader=ChoiceLoader([FileSystemLoader(str(p)) for p in search_paths]),
            autoescape=False,
            undefined=StrictUndefined,  # fail fast if a variable is missing
            trim_blocks=True,
            lstrip_blocks=True,
        )

        template = env.get_template("generate_library.py.j2")

        def deEmojify(text: str) -> str:
            regrex_pattern = re.compile(
                pattern="["
                "\U0001f600-\U0001f64f"  # emoticons
                "\U0001f300-\U0001f5ff"  # symbols & pictographs
                "\U0001f680-\U0001f6ff"  # transport & map symbols
                "\U0001f1e0-\U0001f1ff"  # flags (iOS)
                "]+",
                flags=re.UNICODE,
            )
            return regrex_pattern.sub(r"", text)

        # Render with values drawn from spec (dict) and explicit python_version
        spec.readme_content = deEmojify(spec.readme_content)
        rendered = template.render(
            spec=asdict(spec),
            python_version=spec.python_version,
        )

        script_path = work_dir / "generate_library.py"
        script_path.write_text(rendered, encoding="utf-8")
        self.logger.info(f"Rendered generation script to {script_path}")

        return script_path

    def _build_container(self, work_dir: Path) -> None:
        """Build the Docker container"""
        self.logger.info(f"Building Docker container: {self.container_name}")

        build_cmd = ["docker", "build", "-t", self.container_name, str(work_dir)]

        try:
            result = subprocess.run(
                build_cmd, cwd=work_dir, capture_output=True, text=True, check=True
            )
            self.logger.info("Container built successfully")
            if result.stdout:
                self.logger.debug(f"Build output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to build container: {e.stderr}")
            raise RuntimeError(f"Docker build failed: {e.stderr}") from e

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

        run_cmd = (
            [
                "docker",
                "run",
                "--rm",
                "--name",
                f"{self.container_name}_run",
                "-v",
                f"{output_dir}:/output",
                "-v",
                f"{work_dir / 'generate_library.py'}:/workspace/generate_library.py",
            ]
            + env_vars
            + [self.container_name, "python", "/workspace/generate_library.py"]
        )

        try:
            self.logger.info("Starting container execution...")

            with open(log_file, "w", encoding="utf-8") as log_f:
                with subprocess.Popen(
                    run_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    encoding="utf-8",
                ) as process:

                    # Stream output in real-time
                    if process.stdout:
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
                "log_file": str(log_file),
            }

        except subprocess.TimeoutExpired as te:
            self.logger.error("Container execution timed out")

            subprocess.run(
                ["docker", "kill", f"{self.container_name}_run"],
                capture_output=True,
                check=True,
            )
            raise RuntimeError(
                f"Container execution timed out after {self.config.timeout_seconds} seconds"
            ) from te

        except subprocess.CalledProcessError as e:
            self.logger.error(
                f"Container execution failed with exit code {e.returncode}"
            )
            error_info = {
                "error": "Container execution failed",
                "exit_code": e.returncode,
            }

            # Try to read error logs
            if log_file.exists():
                error_info["logs"] = log_file.read_text(encoding="utf-8")

            raise RuntimeError(f"Container execution failed: {error_info}") from e

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
                subprocess.run(
                    ["docker", "rmi", self.container_name],
                    capture_output=True,
                    check=False,
                )

                self.logger.info("Library generation completed successfully")
                return result

            except Exception as e:
                self.logger.error(f"Library generation failed: {e}")

                # Cleanup on failure
                subprocess.run(
                    ["docker", "rmi", self.container_name],
                    capture_output=True,
                    check=False,
                )

                raise

    def list_generated_libraries(self) -> List[Dict[str, Any]]:
        """List all generated libraries in the cache"""
        libraries = []

        for output_dir in self.cache_path.glob("output_*"):
            if output_dir.is_dir():
                summary_file = output_dir / "generation_summary.json"
                if summary_file.exists():
                    with open(summary_file, encoding="utf-8") as f:
                        summary = json.load(f)
                        summary["output_path"] = str(output_dir)
                        libraries.append(summary)

        return sorted(libraries, key=lambda x: x.get("generation_timestamp", ""))

    def cleanup_cache(self, older_than_days: int = 7) -> int:
        """Remove old generated libraries from cache"""
        cutoff_time = time.time() - (older_than_days * 24 * 3600)
        removed_count = 0

        for output_dir in self.cache_path.glob("output_*"):
            if output_dir.is_dir():
                try:
                    # Extract timestamp from directory name
                    timestamp = int(output_dir.name.split("_")[1])
                    if timestamp < cutoff_time:
                        shutil.rmtree(output_dir)
                        removed_count += 1
                        self.logger.info(f"Removed old cache directory: {output_dir}")
                except (ValueError, IndexError):
                    # Skip directories that don't match the expected naming pattern
                    pass

        return removed_count
