"""
OpenRouter AI client for generating PyPI-style search results.
"""

import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
from .models import SearchResult, SearchResponse
from .config import config
from .package_cache import package_cache


class OpenRouterClient:
    """Client for interacting with OpenRouter AI service via OpenAI interface."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
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
                                 "You should return realistic package information in the exact JSON format requested."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
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
                info={"query": query, "count": len(results)},
                results=results
            )
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Content: {content}")
            return SearchResponse()
        except Exception as e:
            print(f"Error parsing AI response: {e}")
            return SearchResponse()