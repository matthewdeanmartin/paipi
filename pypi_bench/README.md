# LLM Package Knowledge Evaluator

A comprehensive tool for evaluating Large Language Models' knowledge of Python packages through three different test scenarios. The tool uses real PyPI data as ground truth and includes aggressive caching to minimize API costs.

## Features

- **Three Evaluation Types**:
  - Mixed package identification (real vs fake packages)
  - Topic-based package generation (generate real packages for a topic)
  - Fake package detection (identify non-existent packages)

- **Cost Optimization**:
  - Aggressive response caching by model, prompt, and temperature
  - Local PyPI index caching with configurable TTL
  - Concurrent request limiting to avoid rate limits

- **Rich Analytics**:
  - Success rate comparisons across models
  - Execution time analysis
  - Detailed confusion matrices
  - Beautiful visualizations with matplotlib and seaborn

- **Ground Truth Validation**:
  - Downloads complete PyPI package index
  - Validates all responses against real package data
  - Generates convincing fake package names for testing

## Installation

1. Clone the repository or download the files
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Get your OpenRouter API key from [openrouter.ai](https://openrouter.ai)

## Quick Start

### Basic Usage
```bash
# Quick evaluation with default models
python run_evaluation.py --api-key your-openrouter-key-here

# Test specific models
python run_evaluation.py --api-key your-key --models "openai/gpt-4o" "anthropic/claude-3.5-sonnet"

# Test multiple topics
python run_evaluation.py --api-key your-key --topics web ml data testing
```

### Using Configuration File
1. Copy `config_example.json` to `config.json`
2. Add your API key and customize settings
3. Run: `python run_evaluation.py --config config.json`

### Programmatic Usage
```python
import asyncio
from llm_package_evaluator import Config, main

# Customize configuration
config = Config()
config.openrouter_api_key = "your-api-key"
config.test_package_count = 25

# Run full evaluation
asyncio.run(main())
```

## Configuration

### Basic Settings
```json
{
  "openrouter_api_key": "your-api-key-here",
  "models_to_test": [
    "openai/gpt-4o",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-pro"
  ],
  "evaluation_settings": {
    "test_package_count": 25,
    "max_concurrent_requests": 5,
    "request_timeout": 30
  }
}
```

### Cache Settings
- `pypi_cache_ttl_days`: How long to cache PyPI index (default: 1 day)
- `response_cache_ttl_days`: How long to cache model responses (default: 7 days)
- `enable_aggressive_caching`: Cache by model + prompt hash to avoid duplicate API calls

### Output Options
Results are saved to:
- `results/summary_results.csv`: High-level metrics
- `results/detailed_results.json`: Complete evaluation data
- `plots/success_rates_comparison.png`: Model comparison chart
- `plots/performance_heatmap.png`: Performance heatmap
- `plots/execution_times.png`: Timing analysis

## Evaluation Details

### 1. Mixed Package Test
- 25 packages (50/50 real/fake split)
- Tests basic package existence knowledge
- CSV response format: `package_name,is_real`

### 2. Topic Generation Test
- Generate 25 real packages for a given topic
- Tests domain-specific package knowledge
- Validates against actual PyPI packages

### 3. Fake Detection Test
- 25 obviously fake package names
- Tests ability to identify non-existent packages
- Measures false positive rate

## Supported Models

The tool works with any OpenRouter-supported model. Popular choices include:

- **OpenAI**: `gpt-4o`, `gpt-4o-mini`
- **Anthropic**: `claude-3.5-sonnet`, `claude-3-haiku`
- **Google**: `gemini-pro`, `gemini-flash`
- **Meta**: `llama-3.1-70b-instruct`, `llama-3.1-405b-instruct`
- **Others**: Check [OpenRouter models](https://openrouter.ai/models) for full list

## Cost Management

The tool includes several cost optimization features:

1. **Response Caching**: Identical requests are never sent twice
2. **Concurrent Limiting**: Prevents rate limit penalties
3. **Ground Truth Caching**: PyPI index downloaded once per day
4. **Quick Mode**: `--quick` flag runs smaller tests for development

Estimated costs (per model per full evaluation):
- Small models (7B-13B): ~$0.10-0.50
- Medium models (70B): ~$1-3
- Large models (GPT-4): ~$5-15

## Example Output

```
EVALUATION SUMMARY
==================================================

openai/gpt-4o:
  mixed_packages: 84.00% (21/25)
  topic_generation_web: 96.00% (24/25)
  fake_detection: 76.00% (19/25)

anthropic/claude-3.5-sonnet:
  mixed_packages: 88.00% (22/25)
  topic_generation_web: 92.00% (23/25)
  fake_detection: 80.00% (20/25)
```

## Advanced Usage

### Custom Test Generation
```python
from llm_package_evaluator import PackageTestGenerator

# Generate custom test cases
generator = PackageTestGenerator(all_packages)
custom_test = generator.generate_mixed_test(count=50)
topic_packages = generator.generate_topic_packages("machine learning", 30)
```

### Custom Analysis
```python
from llm_package_evaluator import ResultsAnalyzer

analyzer = ResultsAnalyzer(config)
analyzer.plot_success_rates(results)
analyzer.create_summary_report(results)
```

## Troubleshooting

### Common Issues

**API Key Errors**
- Ensure your OpenRouter API key is valid
- Check your OpenRouter account has sufficient credits

**Cache Issues**
- Delete `cache/` directory to force refresh
- Check disk space for PyPI index (~100MB)

**Model Errors**
- Verify model names match OpenRouter exactly
- Some models may have context length limits

**Memory Issues**
- Reduce `max_concurrent_requests` in config
- Use `--quick` flag for testing

### Debug Mode
```bash
python run_evaluation.py --verbose --api-key your-key
```

## Contributing

This tool is designed to be easily extensible:

1. **New Evaluation Types**: Add methods to `EvaluationEngine`
2. **Custom Models**: Modify `OpenRouterClient` for other APIs
3. **Analysis Features**: Extend `ResultsAnalyzer` with new metrics
4. **Visualization**: Add plots to the analysis module

## License

MIT License - feel free to modify and distribute.

## Changelog

### v1.0.0
- Initial release with three evaluation types
- Full PyPI integration and caching
- Beautiful visualizations
- Cost optimization features