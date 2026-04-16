from datetime import datetime

from paipi.models import (
    PackageFile,
    PackageGenerateRequest,
    PackageRelease,
    ProjectDetails,
    ProjectInfo,
    ProjectUrls,
    ReadmeRequest,
    ReadmeResponse,
    SearchResponse,
    SearchResult,
)


def test_project_info():
    info = ProjectInfo(name="test-pkg", version="1.0.0", description="A test package")
    assert info.name == "test-pkg"
    assert info.version == "1.0.0"
    assert info.description == "A test package"


def test_project_urls():
    urls = ProjectUrls(
        homepage="https://example.com", repository="https://github.com/test/test"
    )
    assert urls.homepage == "https://example.com"
    assert urls.repository == "https://github.com/test/test"
    assert urls.documentation is None


def test_project_details():
    details = ProjectDetails(
        author="John Doe",
        classifiers=["License :: OSI Approved :: MIT License"],
        project_urls=ProjectUrls(homepage="https://example.com"),
    )
    assert details.author == "John Doe"
    assert "License :: OSI Approved :: MIT License" in details.classifiers
    assert details.project_urls.homepage == "https://example.com"


def test_package_release():
    now = datetime.now()
    release = PackageRelease(version="1.0.0", upload_time=now)
    assert release.version == "1.0.0"
    assert release.upload_time == now
    assert not release.yanked


def test_package_file():
    file = PackageFile(
        filename="test-1.0.0.tar.gz",
        url="https://example.com/test.tar.gz",
        hashes={"sha256": "fakehash"},
        size=1024,
    )
    assert file.filename == "test-1.0.0.tar.gz"
    assert file.hashes["sha256"] == "fakehash"
    assert file.size == 1024
    assert file.packagetype == "sdist"


def test_search_result():
    result = SearchResult(
        name="test-pkg", version="1.0.0", summary="A test", package_exists=True
    )
    assert result.name == "test-pkg"
    assert result.package_exists is True
    assert result.readme_cached is False


def test_search_response():
    resp = SearchResponse(
        info={"query": "test"}, results=[SearchResult(name="test-pkg", version="1.0.0")]
    )
    assert resp.info["query"] == "test"
    assert len(resp.results) == 1
    assert resp.results[0].name == "test-pkg"


def test_readme_request():
    req = ReadmeRequest(
        name="test-pkg", summary="A test package", usage_snippets=["import test"]
    )
    assert req.name == "test-pkg"
    assert req.usage_snippets == ["import test"]


def test_readme_response():
    resp = ReadmeResponse(markdown="# Test Pkg\n\nSummary")
    assert resp.markdown == "# Test Pkg\n\nSummary"


def test_package_generate_request():
    req = PackageGenerateRequest(
        readme_markdown="# Test", metadata={"name": "test-pkg", "version": "1.0.0"}
    )
    assert req.readme_markdown == "# Test"
    assert req.metadata["name"] == "test-pkg"
