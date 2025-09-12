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

import re
from typing import Dict, List, Optional

from openai import OpenAI

from .cache_manager import cache_manager
from .client_base import OpenRouterClientBase
from .config import config
from .logger import llm_logger
from .models import SearchResponse, SearchResult
from .package_cache import package_cache


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
    ) -> List[str]:
        """
        Iteratively asks the LLM to generate a list of relevant package names.

        Args:
            query: The user's search query.
            limit: The target number of package names to generate.
            max_iterations: A safeguard to prevent infinite loops.

        Returns:
            A list of unique, cleaned package name strings.
        """
        found_packages: set[str] = set()
        iteration = 0
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
                response = self.client.chat.completions.create(
                    model=config.default_model,
                    messages=messages,  # type: ignore
                    temperature=0.6,
                    max_tokens=1000,
                )
                content = response.choices[0].message.content or ""
                llm_logger.debug(f"RAW LLM Name Response:\n---\n{content}\n---")

                # Add assistant's response to maintain conversation context
                messages.append({"role": "assistant", "content": content})

                # Process the response
                lines = content.strip().split("\n")
                for line in lines:
                    # Clean up the line: remove punctuation, whitespace, list markers
                    cleaned_name = re.sub(r"^[*\-–—\s\d.]+\s*", "", line.strip())
                    cleaned_name = re.sub(r"[^\w.-]+", "", cleaned_name)

                    if cleaned_name and len(cleaned_name) > 1:
                        found_packages.add(cleaned_name)
                        if len(found_packages) >= limit:
                            break

            except Exception as e:
                llm_logger.error(f"Error during package name generation: {e}")
                break  # Exit loop on API error

        return list(found_packages)[:limit]

    def _generate_metadata_for_fake_packages(
        self, package_names: List[str], query: str, batch_size: int = 3
    ) -> Dict[str, SearchResult]:
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
            return {}

        generated_results = {}
        for i in range(0, len(package_names), batch_size):
            batch = package_names[i : i + batch_size]
            llm_logger.info(f"Generating metadata for fake packages batch: {batch}")

            prompt = self._build_metadata_prompt(batch, query)
            try:
                response = self.client.chat.completions.create(
                    model=config.default_model,
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
                content = response.choices[0].message.content
                llm_logger.debug(
                    f"RAW LLM Metadata Response for {batch}:\n---\n{content}\n---"
                )
                if not content:
                    continue

                data = self.base.parse_and_repair_json(content)
                for item in data.get("results", []):
                    try:
                        result = SearchResult(**item)
                        # Mark as non-existent but with generated data
                        result.package_exists = False
                        generated_results[result.name] = result
                    except Exception as e:
                        llm_logger.warning(
                            f"Error parsing generated metadata item: {e}\nItem: {item}"
                        )

            except Exception as e:
                llm_logger.error(
                    f"Error querying OpenRouter for metadata generation: {e}"
                )
                continue

        return generated_results

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
        candidate_names = self._generate_package_name_candidates(query, limit)
        if not candidate_names:
            return SearchResponse()

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
        fake_package_metadata = self._generate_metadata_for_fake_packages(
            fake_package_names, query
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
                )
                final_results.append(result)
            elif name in fake_package_metadata:
                # For fake packages, use the generated metadata
                final_results.append(fake_package_metadata[name])

        return SearchResponse(
            info={"query": query, "count": len(final_results)}, results=final_results
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
