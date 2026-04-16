from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from paipi.coder.generate_package import (
    DockerOpenInterpreter,
    GenerationConfig,
    LibrarySpec,
)


@pytest.fixture
def config(tmp_path):
    return GenerationConfig(
        cache_folder=str(tmp_path / "cache"), openai_api_key="fake-key"
    )


@pytest.fixture
def spec():
    return LibrarySpec(
        name="test-lib",
        python_version="3.11",
        pypi_description="Test description",
        readme_content="# Test Lib",
    )


@patch("subprocess.run")
def test_docker_interpreter_init(mock_run, config):
    mock_run.return_value = MagicMock(stdout="Docker version 20.10.7")
    doi = DockerOpenInterpreter(config)
    assert doi.config.openai_api_key == "fake-key"
    mock_run.assert_called_with(
        ["docker", "--version"], capture_output=True, text=True, check=True
    )


@patch("subprocess.run")
def test_docker_interpreter_init_fail(mock_run, config):
    mock_run.side_effect = FileNotFoundError
    with pytest.raises(RuntimeError, match="Docker is not installed"):
        DockerOpenInterpreter(config)


def test_library_spec_post_init():
    spec = LibrarySpec(
        name="test",
        python_version="3.8",
        pypi_description="desc",
        readme_content="readme",
    )
    assert spec.additional_requirements == []


@patch("subprocess.run")
@patch("subprocess.Popen")
def test_generate_library_flow(mock_popen, mock_run, config, spec, tmp_path):
    # Mock docker version check
    mock_run.return_value = MagicMock(stdout="Docker version 20.10.7")

    doi = DockerOpenInterpreter(config)

    # Mock subprocess.run for build and rmi
    mock_run.return_value = MagicMock(returncode=0, stdout="success")

    # Mock subprocess.Popen for container run
    mock_process = MagicMock()
    mock_process.__enter__.return_value = mock_process
    mock_process.stdout = ["line 1\n", "line 2\n"]
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    # We need to mock the template rendering or ensure it works
    # If we don't mock it, it will try to read from paipi/coder/templates

    with patch.object(doi, "_create_generation_script") as mock_script:
        mock_script.return_value = Path("fake_script.py")
        result = doi.generate_library(spec)

    assert result["status"] == "success"
    assert "output_directory" in result
    assert mock_run.call_count >= 2  # --version and build (and rmi)
    mock_popen.assert_called()


def test_cleanup_cache(config, tmp_path):
    # Mock docker version check
    with patch("subprocess.run"):
        doi = DockerOpenInterpreter(config)

    # Create some fake output directories
    import time

    now = int(time.time())
    old = now - (10 * 24 * 3600)  # 10 days ago

    (doi.cache_path / f"output_{now}").mkdir()
    (doi.cache_path / f"output_{old}").mkdir()

    removed = doi.cleanup_cache(older_than_days=7)
    assert removed == 1
    assert (doi.cache_path / f"output_{now}").exists()
    assert not (doi.cache_path / f"output_{old}").exists()
