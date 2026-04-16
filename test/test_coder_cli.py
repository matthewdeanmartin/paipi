from unittest.mock import MagicMock, patch


from paipi.coder.cli import main


@patch("paipi.coder.cli.DockerOpenInterpreter")
@patch("argparse.ArgumentParser.parse_args")
def test_coder_cli_generate(mock_args, mock_doi):
    mock_args.return_value = MagicMock(
        name="test-lib",
        description="desc",
        readme="readme",
        python_version="3.11",
        cache_folder="./cache",
        openai_api_key="key",
        model="gpt-4",
        timeout=3600,
        list=False,
        cleanup=None,
    )

    mock_interpreter = mock_doi.return_value
    mock_interpreter.generate_library.return_value = {
        "output_directory": "/tmp/out",
        "log_file": "/tmp/log",
    }

    with patch("builtins.print") as mock_print:
        main()

    mock_interpreter.generate_library.assert_called_once()
    mock_print.assert_any_call("✅ Library generated successfully!")


@patch("paipi.coder.cli.DockerOpenInterpreter")
@patch("argparse.ArgumentParser.parse_args")
def test_coder_cli_list(mock_args, mock_doi):
    mock_args.return_value = MagicMock(
        list=True,
        cleanup=None,
        python_version="3.11",
        cache_folder="./cache",
        timeout=3600,
        openai_api_key="key",
        model="gpt-4",
    )

    mock_interpreter = mock_doi.return_value
    mock_interpreter.list_generated_libraries.return_value = [
        {
            "library_name": "lib1",
            "generation_timestamp": "2024-01-01",
            "output_path": "/path/1",
        }
    ]

    with patch("builtins.print") as mock_print:
        main()

    mock_print.assert_any_call("Generated libraries:")
    mock_print.assert_any_call("  - lib1 (2024-01-01)")


@patch("paipi.coder.cli.DockerOpenInterpreter")
@patch("argparse.ArgumentParser.parse_args")
def test_coder_cli_cleanup(mock_args, mock_doi):
    mock_args.return_value = MagicMock(
        list=False,
        cleanup=7,
        python_version="3.11",
        cache_folder="./cache",
        timeout=3600,
        openai_api_key="key",
        model="gpt-4",
    )

    mock_interpreter = mock_doi.return_value
    mock_interpreter.cleanup_cache.return_value = 5

    with patch("builtins.print") as mock_print:
        main()

    mock_interpreter.cleanup_cache.assert_called_with(7)
    mock_print.assert_any_call("Removed 5 old cache directories.")
