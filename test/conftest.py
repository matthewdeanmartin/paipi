import pytest

from paipi.cache_manager import CacheManager
from paipi.package_cache import PackageCache


@pytest.fixture
def test_caches(tmp_path, monkeypatch):
    test_cache_dir = tmp_path / "pypi_cache"
    test_db_path = tmp_path / "paipi_cache.db"

    # Reset singletons if they exist

    PackageCache._instance = None

    test_cm = CacheManager(cache_dir=test_cache_dir)
    test_pc = PackageCache(db_path=test_db_path)

    # Patch across all potential import locations
    for module in [
        "paipi.main",
        "paipi.client_search",
        "paipi.cache_manager",
        "paipi.package_cache",
    ]:
        try:
            monkeypatch.setattr(f"{module}.cache_manager", test_cm)
        except AttributeError:
            pass
        try:
            monkeypatch.setattr(f"{module}.package_cache", test_pc)
        except AttributeError:
            pass

    try:
        yield test_cm, test_pc
    finally:
        test_cm.close()
        test_pc.close()
        PackageCache._instance = None
