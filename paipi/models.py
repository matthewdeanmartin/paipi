"""
Pydantic models for PyPI-shaped API responses with type hints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProjectInfo(BaseModel):
    """Basic project information."""

    name: str
    version: str
    description: Optional[str] = None


class ProjectUrls(BaseModel):
    """Project URLs."""

    homepage: Optional[str] = None
    repository: Optional[str] = None
    documentation: Optional[str] = None
    download: Optional[str] = None


class ProjectDetails(BaseModel):
    """Detailed project information."""

    author: Optional[str] = None
    author_email: Optional[str] = None
    maintainer: Optional[str] = None
    maintainer_email: Optional[str] = None
    license: Optional[str] = None
    keywords: Optional[str] = None
    classifiers: List[str] = Field(default_factory=list)
    requires_python: Optional[str] = None
    project_urls: Optional[ProjectUrls] = None
    summary: Optional[str] = None
    platform: Optional[str] = None


class PackageRelease(BaseModel):
    """Package release information."""

    version: str
    yanked: bool = False
    yanked_reason: Optional[str] = None
    upload_time: Optional[datetime] = None


class PackageFile(BaseModel):
    """Package file information."""

    filename: str
    url: str
    hashes: Dict[str, str] = Field(default_factory=dict)
    requires_python: Optional[str] = None
    yanked: bool = False
    yanked_reason: Optional[str] = None
    upload_time: Optional[datetime] = None
    size: Optional[int] = None
    packagetype: str = "sdist"  # sdist, bdist_wheel, etc.


class SearchResult(BaseModel):
    """Individual search result matching PyPI format."""

    name: str
    version: str
    description: Optional[str] = None
    summary: Optional[str] = None
    author: Optional[str] = None
    author_email: Optional[str] = None
    maintainer: Optional[str] = None
    maintainer_email: Optional[str] = None
    home_page: Optional[str] = None
    package_url: Optional[str] = None
    release_url: Optional[str] = None
    docs_url: Optional[str] = None
    download_url: Optional[str] = None
    bugtrack_url: Optional[str] = None
    keywords: Optional[str] = None
    license: Optional[str] = None
    classifiers: List[str] = Field(default_factory=list)
    platform: Optional[str] = None
    requires_python: Optional[str] = None
    project_urls: Dict[str, str] = Field(default_factory=dict)
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


class SearchResponse(BaseModel):
    """PyPI search API response format."""

    info: Dict[str, Any] = Field(default_factory=dict)
    results: List[SearchResult] = Field(default_factory=list)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ReadmeRequest(BaseModel):
    """Input metadata to draft a README."""

    name: str = Field(..., description="Project/package name")
    summary: Optional[str] = Field(None, description="One-line summary / tagline")
    description: Optional[str] = Field(None, description="Longer description")
    license: Optional[str] = None
    repo_url: Optional[str] = None
    homepage: Optional[str] = None
    documentation_url: Optional[str] = None
    install_cmd: Optional[str] = Field(None, description="e.g., pip install yourpkg")
    python_requires: Optional[str] = None
    features: Optional[List[str]] = None
    usage_snippets: Optional[List[str]] = Field(
        default=None, description="Code examples as raw code strings"
    )
    extras: Optional[Dict[str, Any]] = Field(
        default=None, description="Any additional metadata you want to pass through"
    )


class ReadmeResponse(BaseModel):
    """Markdown payload for README.md as a raw string."""

    markdown: str


class PackageGenerateRequest(BaseModel):
    """Stub: payload that will be sent to LLM to generate a package."""

    readme_markdown: str
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Everything needed to assemble a package (name, version, pyproject, module skeleton, etc.)",
    )
