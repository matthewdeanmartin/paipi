"""
Pydantic models for PyPI-shaped API responses with type hints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectInfo(BaseModel):
    """Basic project information."""

    name: str
    version: str
    description: str | None = None


class ProjectUrls(BaseModel):
    """Project URLs."""

    homepage: str | None = None
    repository: str | None = None
    documentation: str | None = None
    download: str | None = None


class ProjectDetails(BaseModel):
    """Detailed project information."""

    author: str | None = None
    author_email: str | None = None
    maintainer: str | None = None
    maintainer_email: str | None = None
    license: str | None = None
    keywords: str | None = None
    classifiers: list[str] = Field(default_factory=list)
    requires_python: str | None = None
    project_urls: ProjectUrls | None = None
    summary: str | None = None
    platform: str | None = None


class PackageRelease(BaseModel):
    """Package release information."""

    version: str
    yanked: bool = False
    yanked_reason: str | None = None
    upload_time: datetime | None = None


class PackageFile(BaseModel):
    """Package file information."""

    filename: str
    url: str
    hashes: dict[str, str] = Field(default_factory=dict)
    requires_python: str | None = None
    yanked: bool = False
    yanked_reason: str | None = None
    upload_time: datetime | None = None
    size: int | None = None
    packagetype: str = "sdist"  # sdist, bdist_wheel, etc.


class SearchResult(BaseModel):
    """Individual search result matching PyPI format."""

    name: str
    version: str
    # Use Field to provide a distinct description for this field in OpenAPI docs
    summary: str | None = Field(
        default=None, description="The short, one-line summary of the package."
    )
    description: str | None = Field(
        default=None,
        description="The long description of the package, typically the README content.",
    )
    author: str | None = None
    author_email: str | None = None
    maintainer: str | None = None
    maintainer_email: str | None = None
    home_page: str | None = None
    package_url: str | None = None
    release_url: str | None = None
    docs_url: str | None = None
    download_url: str | None = None
    bugtrack_url: str | None = None
    keywords: str | None = None
    license: str | None = None
    classifiers: list[str] = Field(default_factory=list)
    platform: str | None = None
    requires_python: str | None = None
    project_urls: dict[str, str] = Field(default_factory=dict)
    package_exists: bool = Field(
        False,
        description="Whether the package name exists on PyPI according to the local cache.",
    )
    readme_cached: bool = Field(
        False,
        description="Whether a README has been generated and cached for this package.",
    )
    package_cached: bool = Field(
        False, description="Whether a generated package ZIP is cached for this package."
    )
    search_model: str | None = Field(
        default=None,
        description="The model used to generate this search result or package suggestion.",
    )
    readme_model: str | None = Field(
        default=None,
        description="The model used to generate the cached README for this package.",
    )
    package_model: str | None = Field(
        default=None,
        description="The model used to generate the cached downloadable package.",
    )


class SearchResponse(BaseModel):
    """PyPI search API response format."""

    info: dict[str, Any] = Field(default_factory=dict)
    results: list[SearchResult] = Field(default_factory=list)
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})


class ReadmeRequest(BaseModel):
    """Input metadata to draft a README."""

    name: str = Field(..., description="Project/package name")
    summary: str | None = Field(None, description="One-line summary / tagline")
    description: str | None = Field(None, description="Longer description")
    license: str | None = None
    repo_url: str | None = None
    homepage: str | None = None
    documentation_url: str | None = None
    install_cmd: str | None = Field(None, description="e.g., pip install yourpkg")
    python_requires: str | None = None
    features: list[str] | None = None
    usage_snippets: list[str] | None = Field(
        default=None, description="Code examples as raw code strings"
    )
    extras: dict[str, Any] | None = Field(
        default=None, description="Any additional metadata you want to pass through"
    )


class ReadmeResponse(BaseModel):
    """Markdown payload for README.md as a raw string."""

    markdown: str


class PackageGenerateRequest(BaseModel):
    """Stub: payload that will be sent to LLM to generate a package."""

    readme_markdown: str
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Everything needed to assemble a package (name, version, pyproject, module skeleton, etc.)",
    )
