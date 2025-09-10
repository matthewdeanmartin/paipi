"""
OpenRouter AI client for generating PyPI-style search results.
"""

import json
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .config import config
from .models import ReadmeRequest, SearchResponse, SearchResult
from .package_cache import package_cache


class OpenRouterClient:
    """Client for interacting with OpenRouter AI service via OpenAI interface."""

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

    def search_packages(self, query: str, limit: int = 20) -> SearchResponse:
        """
        Search for Python packages using AI knowledge.

        Args:
            query: Search query for Python packages
            limit: Maximum number of results to return

        Returns:
            SearchResponse containing AI-generated package results
        """
        prompt = self._build_search_prompt(query, limit)

        try:
            response = self.client.chat.completions.create(
                model=config.default_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that knows about Python packages on PyPI. "
                        "You should return realistic package information in the exact JSON format requested.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=4000,
            )

            content = response.choices[0].message.content
            if not content:
                return SearchResponse()

            # Parse the AI response and convert to our model
            return self._parse_ai_response(content, query)

        except Exception as e:
            # Return empty response on error but log it
            print(f"Error querying OpenRouter: {e}")
            return SearchResponse()

    def _build_search_prompt(self, query: str, limit: int) -> str:
        """Build the prompt for the AI to generate PyPI search results."""
        return f"""
Please search for Python packages related to: "{query}"

Return up to {limit} relevant Python packages in this exact JSON format:
{{
    "results": [
        {{
            "name": "package-name",
            "version": "1.0.0",
            "description": "Brief description of the package",
            "summary": "One-line summary",
            "author": "Author Name",
            "author_email": "author@example.com",
            "home_page": "https://github.com/author/package",
            "package_url": "https://pypi.org/project/package-name/",
            "keywords": "keyword1, keyword2",
            "license": "MIT",
            "classifiers": [
                "Development Status :: 4 - Beta",
                "Intended Audience :: Developers",
                "License :: OSI Approved :: MIT License",
                "Programming Language :: Python :: 3"
            ],
            "requires_python": ">=3.7",
            "project_urls": {{
                "Homepage": "https://github.com/author/package",
                "Repository": "https://github.com/author/package",
                "Documentation": "https://package.readthedocs.io/"
            }}
        }}
    ]
}}

Focus on real, popular Python packages that match the search query. Include accurate information about versions, authors, and descriptions. If you're not certain about specific details, provide reasonable defaults that match typical PyPI package patterns.
"""

    def _parse_ai_response(self, content: str, query: str) -> SearchResponse:
        """Parse the AI response and convert to SearchResponse model."""
        try:
            # Try to extract JSON from the response
            content = content.strip()
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)

            # Convert to our models
            results = []
            for item in data.get("results", []):
                try:
                    result = SearchResult(**item)
                    # Check if the package exists in our cache
                    result.package_exists = package_cache.package_exists(result.name)
                    results.append(result)
                except Exception as e:
                    print(f"Error parsing result item: {e}")
                    continue

            return SearchResponse(
                info={"query": query, "count": len(results)}, results=results
            )

        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Content: {content}")
            return SearchResponse()
        except Exception as e:
            print(f"Error parsing AI response: {e}")
            return SearchResponse()

    # --- add inside OpenRouterClient in client.py ---

    def generate_readme(self, req: "ReadmeRequest") -> str:
        """
        Ask the LLM for a structured JSON README outline, then render to clean Markdown.

        Returns:
            Markdown string suitable for README.md (no JSON punctuation).
        """
        prompt = self._build_readme_prompt(req)

        try:
            response = self.client.chat.completions.create(
                model=config.default_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a senior Python maintainer. "
                            "Return ONLY valid minified JSON. No markdown fences, no commentary."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=4000,
            )

            content = response.choices[0].message.content or ""
            data = self._extract_json(content)
            return self._render_readme_markdown(data)

        except Exception as e:
            print(f"Error generating README via OpenRouter: {e}")
            # Graceful fallback
            return f"# {req.name}\n\n{req.summary or ''}\n\n> README generation failed. Please try again."

    # --- helpers ---

    def _build_readme_prompt(self, req: "ReadmeRequest") -> str:
        """Builds the README generation prompt with strict JSON schema instructions."""
        # minimal context → reduce hallucinated sections, still flexible
        return (
            "Draft a comprehensive README as JSON with these keys:\n"
            "{\n"
            '  "title": str,\n'
            '  "tagline": str,\n'
            '  "badges": [str],\n'
            '  "description": str,\n'
            '  "features": [str],\n'
            '  "installation": { "text": str, "code": str },\n'
            '  "usage": [ { "title": str, "code": str } ],\n'
            '  "configuration": [ { "name": str, "description": str } ],\n'
            '  "links": { "Homepage": str, "Repository": str, "Documentation": str },\n'
            '  "license": str,\n'
            '  "contributing": str,\n'
            '  "faq": [ { "q": str, "a": str } ]\n'
            "}\n\n"
            "Rules:\n"
            "- Return ONLY valid JSON (no code fences, no trailing commas, no comments).\n"
            "- Prefer concise, accurate, copy-pasteable code blocks in `installation.code` and each `usage[].code`.\n"
            "- Omit sections that cannot be populated, or use empty arrays/strings.\n"
            "- Keep badges short (e.g., shields.io). Do not include HTML.\n\n"
            f"Project metadata (authoritative): {json.dumps(req.dict(), ensure_ascii=False)}"
        )

    def _extract_json(self, content: str) -> Dict[str, Any]:
        """
        Extract JSON whether or not the model wrapped it in code fences.
        """
        s = content.strip()
        if s.startswith("```"):
            # tolerate ```json or ``` wrapping
            try:
                s = s.split("```", 1)[1]
                s = s.split("```", 1)[0]
            except Exception:
                pass
        return json.loads(s)

    def _render_readme_markdown(self, data: Dict[str, Any]) -> str:
        """
        Turn the LLM's JSON into tidy, human-friendly Markdown.
        """

        def sec(title: str) -> str:
            return f"\n## {title}\n"

        lines: List[str] = []
        title = data.get("title") or ""
        tagline = data.get("tagline") or ""

        if title:
            lines.append(f"# {title}")
        if tagline:
            lines.append(f"\n> {tagline}")

        # badges
        badges = data.get("badges") or []
        if badges:
            lines.append("")
            for b in badges:
                lines.append(b)

        # description
        desc = (data.get("description") or "").strip()
        if desc:
            lines.append(sec("Description"))
            lines.append(desc)

        # features
        feats = data.get("features") or []
        if feats:
            lines.append(sec("Features"))
            for f in feats:
                lines.append(f"- {f}")

        # installation
        install = data.get("installation") or {}
        if install.get("text") or install.get("code"):
            lines.append(sec("Installation"))
            if install.get("text"):
                lines.append(install["text"])
            if install.get("code"):
                lines.append("\n```bash")
                lines.append(install["code"].strip())
                lines.append("```")

        # usage
        usage = data.get("usage") or []
        if usage:
            lines.append(sec("Usage"))
            for u in usage:
                title = u.get("title")
                code = u.get("code")
                if title:
                    lines.append(f"**{title}**")
                if code:
                    lines.append("\n```python")
                    lines.append(code.strip())
                    lines.append("```")

        # configuration
        cfg = data.get("configuration") or []
        if cfg:
            lines.append(sec("Configuration"))
            for item in cfg:
                name = item.get("name")
                desc = item.get("description")
                if name:
                    lines.append(f"- **{name}** — {desc or ''}".rstrip())

        # links
        links = data.get("links") or {}
        if links:
            lines.append(sec("Links"))
            for k, v in links.items():
                if v:
                    lines.append(f"- [{k}]({v})")

        # contributing
        contrib = data.get("contributing") or ""
        if contrib.strip():
            lines.append(sec("Contributing"))
            lines.append(contrib.strip())

        # license
        license_ = data.get("license") or ""
        if license_.strip():
            lines.append(sec("License"))
            lines.append(license_.strip())

        # faq
        faq = data.get("faq") or []
        if faq:
            lines.append(sec("FAQ"))
            for qa in faq:
                q = qa.get("q")
                a = qa.get("a")
                if q:
                    lines.append(f"**Q:** {q}")
                    if a:
                        lines.append(f"**A:** {a}")
                    lines.append("")

        return "\n".join(lines).strip() + "\n"
