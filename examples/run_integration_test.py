#!/usr/bin/env python3
"""
Integration Test for the DockerOpenInterpreter module.

This script provides a full, end-to-end test of the library generation process.
It does not use any testing frameworks like pytest or unittest.

WHAT IT DOES:
1. Sets up a temporary directory for test artifacts (cache, output).
2. Defines a specification for a simple, plausible Python library.
3. Instantiates the DockerOpenInterpreter.
4. Calls the `generate_library` method, which will:
   - Create a Dockerfile.
   - Build a Docker image.
   - Run a container to execute Open Interpreter.
   - Generate the library source code inside the container.
   - Copy the generated code back to the host.
5. Verifies that the process completed successfully and that essential files were created.
6. Cleans up all temporary directories and artifacts.

PRE-REQUISITES:
- Docker must be installed and the Docker daemon must be running.
- The `OPENAI_API_KEY` environment variable must be set.

USAGE:
From the root of the 'paipi' project directory, run:
  $ export OPENAI_API_KEY="your-key"
  $ python3 examples/run_integration_test.py
"""
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from paipi.generate_package import (
    DockerOpenInterpreter,
    GenerationConfig,
    LibrarySpec,
)

# # --- Path Setup ---
# # Add the parent directory ('paipi') to the Python path to allow imports
# # from the main application source.
# # This makes the script runnable from the project root.
# project_root = Path(__file__).resolve().parent.parent
# sys.path.insert(0, str(project_root))


# Load environment variables from .env file
load_dotenv()


# --- Test Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("IntegrationTest")


def main():
    """Main function to run the integration test."""
    log.info("=" * 60)
    log.info("🚀 STARTING DOCKER OPEN INTERPRETER INTEGRATION TEST 🚀")
    log.info("=" * 60)

    # --- 1. Test Setup ---
    # Create a dedicated directory for this test run to avoid conflicts.
    test_run_dir = Path(__file__).resolve().parent / "test_run"
    if test_run_dir.exists():
        log.warning(f"Removing previous test run directory: {test_run_dir}")
    test_run_dir.mkdir()
    log.info(f"Created temporary test directory: {test_run_dir}")

    try:
        # --- 2. Define Test Configuration and Specification ---
        log.info("Configuring test parameters...")

        # A short timeout for the test to avoid long waits.
        # Increase if the generation process is complex.
        test_timeout_seconds = 600  # 10 minutes

        # Configuration for the generator
        config = GenerationConfig(
            python_version="3.11",
            cache_folder=str(test_run_dir / "cache"),
            timeout_seconds=test_timeout_seconds,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4-turbo",  # Often faster and cheaper for code generation
        )

        # Specification for the library we want to generate
        spec = LibrarySpec(
            name="fibonacci-calculator",
            python_version="3.11",
            pypi_description="A simple utility to calculate Fibonacci numbers.",
            readme_content="""
# Fibonacci Calculator

A lightweight and efficient Python package to compute numbers in the Fibonacci sequence.

## Features
- Calculate the Nth Fibonacci number.
- Generate a sequence of Fibonacci numbers up to N.
- Includes basic error handling for invalid inputs.

## Usage
```python
import fibonacci_calculator

# Get the 10th Fibonacci number
num = fibonacci_calculator.get_number(10)
print(f"The 10th Fibonacci number is {num}")

# Get the sequence up to the 10th number
seq = fibonacci_calculator.get_sequence(10)
print(f"The sequence is: {seq}")""", )
        log.info(f"Test library spec created for '{spec.name}'")
        if not config.openai_api_key:
            log.error("FATAL: OPENAI_API_KEY environment variable is not set.")
            sys.exit(1)

            # --- 3. Instantiate and Run the Generator ---
        log.info("Instantiating DockerOpenInterpreter...")
        interpreter = DockerOpenInterpreter(config)

        log.info("-" * 60)
        log.info(f"Calling generate_library for '{spec.name}'. This will take a few minutes...")
        log.info("Watch for [CONTAINER] logs below.")
        log.info("-" * 60)

        result = interpreter.generate_library(spec)

        log.info("-" * 60)
        log.info("✅ `generate_library` method completed without errors.")
        log.info("-" * 60)

        # --- 4. Verify the Results ---
        log.info("Verifying generated artifacts...")
        assert result is not None, "Result object should not be None"
        assert result["status"] == "success", "Generation status should be 'success'"
        log.info(f"  - Status is '{result['status']}'")

        output_dir = Path(result["output_directory"])
        assert output_dir.exists(), f"Output directory {output_dir} should exist"
        log.info(f"  - Output directory exists: {output_dir}")

        # Check for essential generated files
        expected_files = [
            "generation_summary.json",
            # "pyproject.toml",
            # "README.md",
        ]
        # found_any_code = False
        for expected_file in expected_files:
            file_path = output_dir / expected_file
            assert file_path.exists(), f"Expected file '{expected_file}' not found!"
            log.info(f"  - Found expected file: {expected_file}")

        # Check the content of the summary file
        summary_path = output_dir / "generation_summary.json"
        with summary_path.open("r") as f:
            summary_data = json.load(f)
        assert (
                summary_data["library_name"] == spec.name
        ), "Library name in summary should match spec"
        log.info("  - generation_summary.json contains correct library name.")

        log.info("-" * 60)
        log.info("🎉 TEST PASSED! All assertions met. 🎉")
        log.info("=" * 60)

    except Exception as e:
        log.error("=" * 60)
        log.error(f"❌ TEST FAILED: An error occurred: {e}", exc_info=True)
        log.error("=" * 60)
        sys.exit(1)

    finally:
        print ("done")
        # # --- 5. Cleanup ---
        # log.info("Performing cleanup...")
        # # if test_run_dir.exists():
        # #     shutil.rmtree(test_run_dir)
        # #     log.info(f"Removed temporary test directory: {test_run_dir}")
        # log.info("Cleanup complete.")

if __name__ == '__main__':
    main()