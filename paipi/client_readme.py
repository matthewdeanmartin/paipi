"""
OpenRouter AI client for generating PyPI-style search results and READMEs.

- Keeps existing JSON-based README generator for backward compatibility.
- Adds a new Markdown-first README generator + new FastAPI endpoint sketch.
"""

from __future__ import annotations

import json
import random
from typing import Any, List, Optional

from openai import OpenAI

from .client_base import OpenRouterClientBase
from .config import config
from .logger import llm_logger  # <--- IMPORT THE NEW LOGGER
from .models import ReadmeRequest


class OpenRouterClientReadMe:
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
        self.base = OpenRouterClientBase(api_key, base_url)

    # -----------------
    # README (OLD JSON-BASED) — retained for backward compatibility
    # -----------------
    def generate_readme(self, req: ReadmeRequest) -> str:
        """
        OLD WAY: Ask the LLM for a structured JSON README outline, then render to Markdown.
        Kept for backward compatibility with existing callers.

        Returns:
            Markdown string suitable for README.md
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
            data = self.base.extract_json(content)
            return self._render_readme_markdown(data)

        except Exception as e:
            print(f"Error generating README via OpenRouter: {e}")
            llm_logger.error(
                f"Error generating README via OpenRouter for '{req.name}': {e}"
            )
            # Graceful fallback
            return f"# {req.name}\n\n{req.summary or ''}\n\n> README generation failed. Please try again."

    def _build_readme_prompt(self, req: ReadmeRequest) -> str:
        """Builds the JSON-based README generation prompt (legacy)."""
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

    # -----------------
    # README (NEW MARKDOWN-FIRST)
    # -----------------
    def generate_readme_markdown(self, req: ReadmeRequest) -> str:
        """
        NEW WAY: Ask the LLM to directly produce clean Markdown (no JSON),
        showing project metadata in a human-readable Markdown block.

        Hard rule: The model must **never** tell users to install with `pip install <package>`
        because PyPI already shows that at the top of the project page.
        """
        prompt = self._build_readme_md_prompt(req)

        try:
            response = self.client.chat.completions.create(
                model=config.default_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a senior Python maintainer and technical writer. "
                            "Return ONLY a complete, well-structured Markdown README. No JSON, no YAML, no HTML wrappers, no code fences around the entire document."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=4000,
            )

            content = response.choices[0].message.content or ""
            llm_logger.debug(
                f"[generate_readme_markdown for {req.name}] RAW LLM RESPONSE:\n---\n{content[:2000]}\n---"
            )
            # Best-effort light cleanup: strip stray outer fences if model adds them
            s = content.strip()
            if s.startswith("```") and s.endswith("```"):
                try:
                    s = s.split("\n", 1)[1]
                    s = s.rsplit("```", 1)[0]
                except Exception:
                    pass
            return s.strip() + ("\n" if not s.endswith("\n") else "")

        except Exception as e:
            print(f"Error generating README (markdown) via OpenRouter: {e}")
            llm_logger.error(
                f"Error generating README (markdown) via OpenRouter for '{req.name}': {e}"
            )
            return f"# {req.name}\n\n{req.summary or ''}\n\n> README generation failed. Please try again."

    def _build_readme_md_prompt(self, req: ReadmeRequest) -> str:
        """Create a Markdown-first README prompt with randomized, varied guidance."""
        meta = req.dict()

        # Present metadata as Markdown (not JSON)
        meta_md: List[str] = [
            f"**Name:** {meta.get('name','')}",
            f"**Summary:** {meta.get('summary','')}",
            f"**Description:** {meta.get('description','')}",
            f"**Homepage:** {meta.get('homepage','')}",
            f"**Repository:** {meta.get('repository','')}",
            f"**Documentation:** {meta.get('documentation','')}",
            f"**Keywords:** {', '.join(meta.get('keywords', []) or [])}",
            f"**License:** {meta.get('license','')}",
            f"**Requires Python:** {meta.get('requires_python','')}",
        ]
        meta_block = "\n".join(["### Project Metadata", "", *meta_md])

        # Instruction pool (we'll sample 6–12 each time to avoid repetition)
        instruction_pool = [
            "Start with an H1 title and an optional one-line tagline.",
            "Use short, descriptive badges if appropriate (e.g., shields.io).",
            "Provide a clear project description focusing on real capabilities.",
            "List key features in bullet points.",
            "Add a quickstart section that shows an immediate, minimal example.",
            "Include usage examples with copy-pasteable code blocks.",
            "Document configuration options succinctly in bullets or a simple table.",
            "Explain how to run tests and where to file issues.",
            "Keep sections concise and scannable; avoid marketing fluff.",
            "Use fenced code blocks for commands and Python snippets only.",
            "Include links (Homepage, Repository, Documentation) in a dedicated section.",
            "Close with License and Contributing notes.",
            "Avoid suggesting `pip install <package>`; PyPI already shows that prominently.",
            "Prefer practical examples over long prose; assume intermediate Python users.",
        ]
        k = random.randint(6, 12)
        sampled_instructions = random.sample(instruction_pool, k)

        # Pinned rules — always included
        pinned_rules = [
            "Return ONLY a Markdown document (no JSON/YAML wrappers).",
            "Do NOT say `pip install <package>` anywhere in the document.",
            "Avoid telling users to `pip install` in any form; assume PyPI page covers installation.",
            "Keep code blocks minimal and runnable.",
        ]

        bullet_lines = "\n".join([f"- {line}" for line in sampled_instructions])
        pinned_lines = "\n".join([f"- {line}" for line in pinned_rules])

        prompt = (
            f"Create a high-quality README.md in **pure Markdown** for the project below.\n\n"
            f"{meta_block}\n\n"
            "Follow these guidelines (varied each time):\n"
            f"{bullet_lines}\n\n"
            "Always enforce these rules:\n"
            f"{pinned_lines}\n\n"
            "Return only the README content."
        )
        return prompt

    def _render_readme_markdown(self, data: dict[str, Any]) -> str:
        """
        Turn the LLM's JSON into tidy, human-friendly Markdown. (Legacy path)
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
