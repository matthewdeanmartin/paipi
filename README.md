# PAIPI - AI-Powered PyPI Search

PyPI search, except the backend is an LLM's pixelated memory of PyPI.

A FastAPI server that provides PyPI-shaped search results powered by AI instead of a traditional database. The server queries OpenRouter's AI service via an OpenAI-compatible interface to generate realistic Python package search results.

## Features

- FastAPI-based REST API with automatic OpenAPI documentation
- PyPI-compatible search response format
- AI-powered package search using OpenRouter
- Type hints throughout the codebase
- Configurable via environment variables

## Installation

```bash
pip install -e .
```

## Configuration

Copy `.env.example` to `.env` and configure your settings:

```bash
cp .env.example .env
```

Required environment variables:
- `OPENROUTER_API_KEY`: Your OpenRouter API key

Optional environment variables:
- `OPENROUTER_BASE_URL`: OpenRouter API base URL (default: https://openrouter.ai/api/v1)
- `OPENROUTER_MODEL`: AI model to use (default: anthropic/claude-3.5-sonnet)
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)
- `DEBUG`: Enable debug mode (default: false)

## Usage

### Running the server

```bash
# Using the CLI command
paipi

# Or directly with Python
python -m paipi.main

# Or with uvicorn
uvicorn paipi.main:app --host 0.0.0.0 --port 8000
```

### API Endpoints

- `GET /` - Root endpoint with basic information
- `GET /health` - Health check endpoint
- `GET /search?q=<query>` - Search for Python packages
- `GET /docs` - Interactive API documentation
- `GET /redoc` - Alternative API documentation

### Search Example

```bash
curl "http://localhost:8000/search?q=web+framework&size=5"
```

Response format matches PyPI search API:
```json
{
  "info": {
    "query": "web framework",
    "count": 5
  },
  "results": [
    {
      "name": "fastapi",
      "version": "0.104.1",
      "description": "FastAPI framework, high performance, easy to learn...",
      "summary": "Modern, fast web framework for building APIs",
      "author": "Sebastián Ramirez",
      "home_page": "https://github.com/tiangolo/fastapi",
      "package_url": "https://pypi.org/project/fastapi/",
      "keywords": "web, api, framework, fastapi",
      "license": "MIT",
      "classifiers": [...],
      "requires_python": ">=3.7"
    }
  ]
}
```

## Development

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Format code:
```bash
black paipi/
isort paipi/
```

Type checking:
```bash
mypy paipi/
```

## License

MIT
