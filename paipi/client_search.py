"""
OpenRouter AI client for generating PyPI-style search results and READMEs.

This version implements a new workflow:
1.  Iteratively asks the LLM for a plain-text list of relevant package names.
2.  Filters and validates the generated names.
3.  Checks for the actual existence of each package against a cache.
4.  Separates packages into 'real' and 'fake' lists.
5.  For 'fake' packages, makes a separate LLM call in batches to generate realistic metadata.
6.  For 'real' packages, it returns them to be handled by a PyPI scraper, preserving the original relevance-based order.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from openai import OpenAI

from .cache_manager import cache_manager
from .client_base import OpenRouterClientBase
from .config import config
from .logger import llm_logger
from .models import SearchResponse, SearchResult
from .package_cache import package_cache
from .package_names import (
    canonicalize_package_name,
    extract_candidate_package_name,
    is_pep503_normalized,
    is_valid_package_name,
)


class SearchGenerationError(RuntimeError):
    """Raised when AI-backed search fails and the UI should show the real error."""


class OpenRouterClientSearch:
    """
    Client for interacting with OpenRouter AI service via OpenAI interface.
    Implements a multi-step process to generate and validate package search results.
    """

    def __init__(
        self, api_key: Optional[str] = None, base_url: Optional[str] = None
    ) -> None:
        """Initialize the OpenRouter client."""
        self.api_key = api_key or config.openrouter_api_key
        self.base_url = base_url or config.openrouter_base_url

        if not self.api_key:
            raise ValueError("OpenRouter API key is required")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
        self.base = OpenRouterClientBase(api_key, base_url)

    def _generate_package_name_candidates(
        self, query: str, limit: int, max_iterations: int = 5
    ) -> tuple[List[str], Optional[str], list[str]]:
        """
        Iteratively asks the LLM to generate a list of relevant package names.

        Args:
            query: The user's search query.
            limit: The target number of package names to generate.
            max_iterations: A safeguard to prevent infinite loops.

        Returns:
            A list of unique, cleaned package name strings.
        """
        found_packages: list[str] = []
        found_package_names: set[str] = set()
        iteration = 0
        model_used: Optional[str] = None
        attempted_models: list[str] = []
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant expert in Python packages. "
                    "Your task is to suggest relevant PyPI package names based on a query. "
                    "Return only a plain text list, with one package name per line."
                ),
            },
        ]

        while len(found_packages) < limit and iteration < max_iterations:
            iteration += 1
            num_needed = limit - len(found_packages)

            prompt = f'Based on the query "{query}", suggest {num_needed} relevant Python package names.'
            if found_packages:
                prompt += (
                    "\n\nAvoid suggesting the following packages that have already been found: "
                    f'{", ".join(sorted(list(found_packages)))}'
                )
            prompt += "\n\nReturn only the package names, one per line."

            # Update the last user message or add a new one
            if messages[-1]["role"] == "user":
                messages[-1]["content"] = prompt
            else:
                messages.append({"role": "user", "content": prompt})

            try:
                llm_logger.debug(
                    f"Name Generation Iteration {iteration}: Requesting {num_needed} packages."
                )
                response = self.base.create_chat_completion(
                    messages=messages,  # type: ignore
                    temperature=0.6,
                    max_tokens=1000,
                )
                content = response.content
                model_used = response.model_used
                attempted_models = response.attempted_models
                llm_logger.debug(f"RAW LLM Name Response:\n---\n{content}\n---")

                # Process the response
                accepted_candidates: list[str] = []
                lines = content.strip().split("\n")
                for line in lines:
                    stripped_line = line.strip()
                    if not stripped_line:
                        continue

                    candidate_name = extract_candidate_package_name(stripped_line)
                    if candidate_name is None:
                        llm_logger.warning(
                            "Discarding malformed package-name candidate line: %r",
                            stripped_line[:200],
                        )
                        continue

                    if not is_pep503_normalized(candidate_name):
                        llm_logger.info(
                            "Candidate package name is not PEP 503-normalized: %s",
                            candidate_name,
                        )

                    normalized_name = canonicalize_package_name(candidate_name)
                    if normalized_name in found_package_names:
                        continue

                    found_package_names.add(normalized_name)
                    found_packages.append(candidate_name)
                    accepted_candidates.append(candidate_name)
                    if len(found_packages) >= limit:
                        break

                if accepted_candidates:
                    messages.append({"role": "assistant", "content": content})
                else:
                    llm_logger.warning(
                        "Ignoring malformed name-generation response that produced no valid package names."
                    )

            except Exception as e:
                message = self.base.format_llm_error(e)
                llm_logger.error(f"Error during package name generation: {message}")
                raise SearchGenerationError(message) from e

        return found_packages[:limit], model_used, attempted_models

    def _generate_metadata_for_fake_packages(
        self, package_names: List[str], query: str, batch_size: int = 3
    ) -> tuple[Dict[str, SearchResult], list[str]]:
        """
        Generates full, realistic-looking metadata for a list of non-existent package names.

        Args:
            package_names: A list of package names confirmed not to exist on PyPI.
            query: The original search query, for context.
            batch_size: The number of packages to process in a single LLM call.

        Returns:
            A dictionary mapping each package name to its generated SearchResult object.
        """
        if not package_names:
            return {}, []

        generated_results: Dict[str, SearchResult] = {}
        metadata_models_used: list[str] = []
        for i in range(0, len(package_names), batch_size):
            batch = package_names[i : i + batch_size]
            requested_by_normalized = {
                canonicalize_package_name(name): name for name in batch
            }
            llm_logger.info(f"Generating metadata for fake packages batch: {batch}")

            prompt = self._build_metadata_prompt(batch, query)
            try:
                response = self.base.create_chat_completion(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful assistant that knows about Python packages. "
                                "You will be given names of packages that DO NOT exist. "
                                "Your task is to generate realistic-looking PyPI metadata for them. "
                                "Return the data in the exact JSON format requested."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=4000,
                )
                content = response.content
                if response.model_used not in metadata_models_used:
                    metadata_models_used.append(response.model_used)
                llm_logger.debug(
                    f"RAW LLM Metadata Response for {batch}:\n---\n{content}\n---"
                )
                if not content:
                    continue

                data = self.base.parse_and_repair_json(content)
                results = data.get("results", [])
                if not isinstance(results, list):
                    llm_logger.warning(
                        "Metadata response did not contain a list under 'results': %r",
                        data,
                    )
                    continue

                for item in results:
                    try:
                        if not isinstance(item, dict):
                            llm_logger.warning(
                                "Discarding malformed metadata item that is not an object: %r",
                                item,
                            )
                            continue

                        raw_name = item.get("name")
                        if not isinstance(raw_name, str) or not is_valid_package_name(
                            raw_name
                        ):
                            llm_logger.warning(
                                "Discarding metadata item with invalid package name: %r",
                                item,
                            )
                            continue

                        if not is_pep503_normalized(raw_name):
                            llm_logger.info(
                                "Metadata package name is not PEP 503-normalized: %s",
                                raw_name,
                            )

                        normalized_name = canonicalize_package_name(raw_name)
                        requested_name = requested_by_normalized.get(normalized_name)
                        if requested_name is None:
                            llm_logger.warning(
                                "Discarding metadata item for unexpected package name %r; expected one of %r",
                                raw_name,
                                batch,
                            )
                            continue

                        if raw_name != requested_name:
                            llm_logger.warning(
                                "Discarding metadata item because package name %r did not exactly match requested name %r",
                                raw_name,
                                requested_name,
                            )
                            continue

                        if requested_name in generated_results:
                            llm_logger.warning(
                                "Discarding duplicate metadata item for package %s",
                                requested_name,
                            )
                            continue

                        normalized_item = dict(item)
                        normalized_item["name"] = requested_name
                        result = SearchResult(**normalized_item)
                        # Mark as non-existent but with generated data
                        result.package_exists = False
                        result.search_model = response.model_used
                        generated_results[requested_name] = result
                    except Exception as e:
                        llm_logger.warning(
                            f"Error parsing generated metadata item: {e}\nItem: {item}"
                        )

            except Exception as e:
                llm_logger.error(
                    "Error querying OpenRouter for metadata generation: %s",
                    self.base.format_llm_error(e),
                )
                continue

        return generated_results, metadata_models_used

    def search_packages(self, query: str, limit: int = 20) -> SearchResponse:
        """
        Search for Python packages using a multi-step AI-driven process.

        Args:
            query: Search query for Python packages.
            limit: Maximum number of results to return.

        Returns:
            SearchResponse containing a mix of real and AI-generated package results,
            maintaining the original order of relevance.
        """
        # Step 1: Generate a list of candidate package names
        candidate_names, candidate_model, attempted_models = (
            self._generate_package_name_candidates(query, limit)
        )
        if not candidate_names:
            return SearchResponse(info={"query": query, "count": 0}, results=[])

        # Step 2: Separate real and fake packages
        real_package_names = []
        fake_package_names = []
        for name in candidate_names:
            if package_cache.package_exists(name):
                real_package_names.append(name)
            else:
                fake_package_names.append(name)

        llm_logger.info(
            f"Verified Packages - Real: {len(real_package_names)}, Fake: {len(fake_package_names)}"
        )

        # Step 3: Generate metadata for the fake packages in batches
        fake_package_metadata, metadata_models_used = (
            self._generate_metadata_for_fake_packages(fake_package_names, query)
        )

        # Step 4: Combine results, preserving original order
        final_results = []
        for name in candidate_names:
            if name in real_package_names:
                # For real packages, create a minimal result. The caller
                # will use the scraper to get full, accurate details.
                result = SearchResult(
                    name=name,
                    version="N/A",  # To be fetched
                    description="This is a real package. Full details will be fetched from PyPI.",
                    package_exists=True,
                    readme_cached=cache_manager.has_readme_by_name(name),
                    package_cached=cache_manager.has_package_by_name(name),
                    search_model=candidate_model,
                )
                final_results.append(result)
            elif name in fake_package_metadata:
                # For fake packages, use the generated metadata
                final_results.append(fake_package_metadata[name])

        return SearchResponse(
            info={
                "query": query,
                "count": len(final_results),
                "model_used": candidate_model,
                "models_tried": attempted_models,
                "metadata_models_used": metadata_models_used,
            },
            results=final_results,
        )

    def _build_metadata_prompt(self, package_names: List[str], query: str) -> str:
        """Build the prompt for the AI to generate metadata for non-existent packages."""
        package_list_str = "\n".join(f"- {name}" for name in package_names)
        return f"""
The following Python packages related to "{query}" do not exist.
Please generate realistic PyPI metadata for them:
{package_list_str}

Return the data in this exact JSON format, with one entry for each requested package:
{{
    "results": [
        {{
            "name": "package-name",
            "version": "1.0.0",
            "description": "Brief, plausible description of what the package might do.",
            "summary": "One-line summary",
            "author": "Generated Author",
            "author_email": "author@example.com",
            "home_page": "https://github.com/author/package-name",
            "package_url": "https://pypi.org/project/package-name/",
            "keywords": "keyword1, keyword2",
            "license": "MIT",
            "classifiers": [
                "Development Status :: 3 - Alpha",
                "Intended Audience :: Developers",
                "License :: OSI Approved :: MIT License",
                "Programming Language :: Python :: 3"
            ],
            "requires_python": ">=3.8",
            "project_urls": {{
                "Homepage": "https://github.com/author/package-name",
                "Repository": "https://github.com/author/package-name"
            }}
        }}
    ]
}}

Ensure the 'name' field in each JSON object exactly matches one of the requested package names.
"""
