"""
Pydantic models for PyPI-shaped API responses with type hints.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


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
    package_exists: bool = Field(False,
                                 description="Whether the package name exists on PyPI according to the local cache.")


class SearchResponse(BaseModel):
    """PyPI search API response format."""
    info: Dict[str, Any] = Field(default_factory=dict)
    results: List[SearchResult] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }