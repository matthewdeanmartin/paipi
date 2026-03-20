from io import BytesIO
import zipfile

import pytest

from paipi.main_package_glue import _normalize_model, _zip_dir_to_bytes


@pytest.mark.parametrize(
    ("model_name", "expected"),
    [
        (None, "gpt-4o-mini"),
        ("gpt4", "gpt-4o"),
        ("gpt-4-turbo", "gpt-4o"),
        ("claude-3.5-sonnet", "gpt-4o"),
        ("unknown-model", "gpt-4o-mini"),
    ],
)
def test_normalize_model_maps_aliases(model_name: str | None, expected: str):
    assert _normalize_model(model_name) == expected


def test_zip_dir_to_bytes_includes_nested_files(tmp_path):
    (tmp_path / "package").mkdir()
    (tmp_path / "package" / "__init__.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Example\n", encoding="utf-8")

    zip_bytes = _zip_dir_to_bytes(tmp_path)

    with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
        names = {name.replace("\\", "/") for name in archive.namelist()}
        assert names == {"README.md", "package/__init__.py"}
        assert archive.read("README.md").decode("utf-8").strip() == "# Example"
