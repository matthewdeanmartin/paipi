# PAIPI - AI-Powered PyPI Search

PyPI search, except the backend is an LLM's pixelated memory of PyPI.

A FastAPI server that provides PyPI-shaped search results powered by AI instead of a traditional database. The server
queries OpenRouter's AI service via an OpenAI-compatible interface to generate realistic Python package search results.

The query can be the same as what you use with pypi or conversational.

The UI shows real packages in blue, hallucinated ones are red. Information for real packages are fetched from pypi.
To hallucinate a README.md, click through to the detail click the generate. Once you have a readme, you can generate
and download a package.

Useful logging on disk as well.

- pypi_cache - packages and sqlite database with real an imagined library info
- logs - raw conversation

This is not exactly RAG. The LLM doesn't search Pypi and tell you the results, the LLM knows a lot of python packages
and can guess if they're relevant. Ordinary code checks if packages are real or not and real packages are displayed
with real information.

## Core Features

- Search for real packages in an LLMs memory
- Hallucinated packages you seem to want to exist and then imagine what their README.md would be
- Generate a package for downloading based on a generated README.md

## Technical Features
- FastAPI-based REST API with automatic OpenAPI documentation
- PyPI-compatible search response format
- AI-powered package search using OpenRouter
- Type hints throughout the codebase
- Configurable via environment variables

## Security
- Don't run this on the open web
- Package generation is inside a docker container

## Installation

To install and run web server

```bash
uv sync
uv run paipi
```

To install and run UI

```bash
cd paipi-app
npm install
ng serve -o
```

To generate packages, docker desktop will need to be running.

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
- `OPENAI_API_KEY`: This is used for package generation using openinterpreter (running inside docer)

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
- `GET /search?q=<query>` - Search for packages
- `POST /readme` - Generate README.md
- `POST /generate_package` - Generate package ZIP
- `GET /cache/stats` - Get cache statistics
- `DELETE /cache/clear` - Clear cache
- `GET /docs` - Interactive API documentation
- `GET /health` - Health check

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
      "classifiers": [
        ...
      ],
      "requires_python": ">=3.7"
    }
  ]
}
```

## Development

Check for python problems:

```bash
make check
```

## License

MIT.

