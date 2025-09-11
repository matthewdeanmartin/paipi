"""
PyPI Scraper client for fetching package metadata from the official JSON API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, cast

import pypi_json
from packaging.requirements import InvalidRequirement
from pydantic import ValidationError
from requests import HTTPError

from .models import (
    PackageFile,
    PackageRelease,
    ProjectDetails,
    ProjectUrls,
)

# Set up a logger for this module, following existing patterns.
scraper_logger = logging.getLogger(__name__)
# Basic config for demonstration if not configured elsewhere
logging.basicConfig(level=logging.INFO)


class PypiScraper:
    """
    A client to fetch and parse package information from the official PyPI JSON API.
    """

    def __init__(self) -> None:
        """Initialize the scraper client."""
        # The pypi_json library is synchronous and class-based.
        # We create one instance to reuse its internal requests.Session.
        self.client = pypi_json.PyPIJSON()

    async def get_project_metadata(
        self, package_name: str, version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches the raw JSON metadata for a package from PyPI.

        Args:
            package_name: The name of the package.
            version: Optional specific version of the package. If None, gets latest.

        Returns:
            A dictionary with the raw package metadata, or None if not found.
        """
        loop = asyncio.get_event_loop()
        try:
            scraper_logger.info(
                f"Fetching metadata for '{package_name}'"
                f"{' version ' + version if version else ' (latest)'}..."
            )
            # The pypi_json library is synchronous, so we run it in an executor
            # to avoid blocking the asyncio event loop.
            metadata_obj = await loop.run_in_executor(
                None, lambda: self.client.get_metadata(package_name, version)
            )

            # The returned object is a NamedTuple; convert it to a dict
            # to match the expected return type used in main.py.
            return metadata_obj._asdict()

        except InvalidRequirement:
            # This exception is raised by pypi_json for 404s.
            scraper_logger.warning(
                f"Package '{package_name}'"
                f"{' version ' + version if version else ''} not found on PyPI."
            )
            return None
        except HTTPError as e:
            # pypi_json uses requests, which raises HTTPError.
            scraper_logger.error(
                f"HTTP error fetching '{package_name}': {e.response.status_code} - {e}"
            )
            return None
        except Exception as e:
            scraper_logger.error(
                f"An unexpected error occurred while fetching '{package_name}': {e}"
            )
            return None

    async def get_project_details(self, package_name: str) -> Optional[ProjectDetails]:
        """
        Fetches detailed information for the latest version of a package.

        Args:
            package_name: The name of the package.

        Returns:
            A ProjectDetails model instance, or None if the package is not found
            or parsing fails.
        """
        metadata = await self.get_project_metadata(package_name)
        if not metadata or "info" not in metadata:
            return None

        info = metadata["info"]
        try:
            project_urls_data = info.get("project_urls")
            project_urls = (
                ProjectUrls(**project_urls_data) if project_urls_data else None
            )

            details = ProjectDetails(
                author=info.get("author"),
                author_email=info.get("author_email"),
                maintainer=info.get("maintainer"),
                maintainer_email=info.get("maintainer_email"),
                license=info.get("license"),
                keywords=info.get("keywords"),
                classifiers=info.get("classifiers", []),
                requires_python=info.get("requires_python"),
                project_urls=project_urls,
                summary=info.get("summary"),
                platform=info.get("platform"),
            )
            return details
        except ValidationError as e:
            scraper_logger.error(
                f"Pydantic validation failed for '{package_name}': {e}"
            )
            return None

    async def get_project_readme(self, package_name: str) -> Optional[str]:
        """
        Fetches only the project's long description (README).

        This is typically the full README content in Markdown or reStructuredText.
        It's separate from the short 'summary'.

        Args:
            package_name: The name of the package.

        Returns:
            The long description string, or None if not found.
        """
        metadata = await self.get_project_metadata(package_name)
        if metadata and "info" in metadata:
            return cast(Optional[str], metadata["info"].get("description"))
        return None

    async def get_all_releases(self, package_name: str) -> List[PackageRelease]:
        """
        Gets a list of all releases for a given package.

        Args:
            package_name: The name of the package.

        Returns:
            A list of PackageRelease objects.
        """
        # Fetch metadata for the project (not a specific version) to get all releases
        metadata = await self.get_project_metadata(package_name)
        if not metadata or not metadata.get("releases"):
            return []

        releases = []
        for version, release_files in metadata["releases"].items():
            if not release_files:
                continue

            is_yanked = all(f.get("yanked", False) for f in release_files)
            yanked_reason = release_files[0].get("yanked_reason") if is_yanked else None
            upload_time = release_files[0].get("upload_time_iso_8061")

            releases.append(
                PackageRelease(
                    version=version,
                    yanked=is_yanked,
                    yanked_reason=yanked_reason,
                    upload_time=upload_time,
                )
            )
        return releases

    async def get_release_files(
        self, package_name: str, version: str = "latest"
    ) -> List[PackageFile]:
        """
        Gets all package files for a specific version of a package.

        Args:
            package_name: The name of the package.
            version: The version string. Defaults to 'latest' to get the newest.

        Returns:
            A list of PackageFile objects for the specified version.
        """
        fetch_version = None if version == "latest" else version
        metadata = await self.get_project_metadata(package_name, version=fetch_version)

        if not metadata:
            return []

        # The files are under the 'urls' key in the JSON response
        files_data = metadata.get("urls", [])
        package_files = []
        try:
            for file_info in files_data:
                package_files.append(
                    PackageFile(
                        filename=file_info.get("filename"),
                        url=file_info.get("url"),
                        hashes=file_info.get("digests", {}),
                        requires_python=file_info.get("requires_python"),
                        yanked=file_info.get("yanked", False),
                        yanked_reason=file_info.get("yanked_reason"),
                        upload_time=file_info.get("upload_time_iso_8601"),
                        size=file_info.get("size"),
                        packagetype=file_info.get("packagetype", "sdist"),
                    )
                )
            return package_files
        except ValidationError as e:
            scraper_logger.error(
                f"Pydantic validation failed for files of '{package_name}': {e}"
            )
            return []
