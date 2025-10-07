"""
LLM Package Knowledge Evaluation Tool

A comprehensive tool for evaluating LLMs' knowledge of Python packages
through three different test scenarios with caching and visualization.
"""

import asyncio
import hashlib
import json
import logging
import pickle
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urljoin

import aiohttp
import matplotlib.pyplot as plt
import pandas as pd
import requests
import seaborn as sns
from tqdm.asyncio import tqdm


# Configuration
@dataclass
class Config:
    """Configuration settings for the evaluation tool."""

    # API Settings
    openrouter_api_key: str = "your-openrouter-api-key-here"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Cache Settings
    cache_dir: Path = Path("cache")
    pypi_cache_ttl: timedelta = timedelta(days=1)
    response_cache_ttl: timedelta = timedelta(days=7)

    # Evaluation Settings
    test_package_count: int = 25
    max_concurrent_requests: int = 5
    request_timeout: int = 30

    # Output Settings
    results_dir: Path = Path("results")
    plots_dir: Path = Path("plots")

    def __post_init__(self) -> None:
        """Create necessary directories."""
        self.cache_dir.mkdir(exist_ok=True)
        self.results_dir.mkdir(exist_ok=True)
        self.plots_dir.mkdir(exist_ok=True)


@dataclass
class EvaluationResult:
    """Results from a single evaluation."""

    model_name: str
    evaluation_type: str
    timestamp: datetime
    success_rate: float
    total_packages: int
    correct_packages: int
    raw_responses: List[str]
    parsed_responses: List[Dict[str, Union[str, bool]]]
    ground_truth: List[Dict[str, Union[str, bool]]]
    execution_time: float
    errors: List[str] = field(default_factory=list)


class PackageIndexManager:
    """Manages PyPI package index with caching."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.cache_file = config.cache_dir / "pypi_index.pkl"
        self.logger = logging.getLogger(__name__)

    async def get_all_packages(self) -> Set[str]:
        """Get all package names from PyPI with caching."""
        if self._is_cache_valid():
            self.logger.info("Loading PyPI index from cache")
            return self._load_cache()

        self.logger.info("Downloading fresh PyPI index...")
        packages = await self._download_packages()
        self._save_cache(packages)
        return packages

    def _is_cache_valid(self) -> bool:
        """Check if the cached index is still valid."""
        if not self.cache_file.exists():
            return False

        cache_age = datetime.now() - datetime.fromtimestamp(
            self.cache_file.stat().st_mtime
        )
        return cache_age < self.config.pypi_cache_ttl

    def _load_cache(self) -> Set[str]:
        """Load cached package index."""
        with open(self.cache_file, 'rb') as f:
            return pickle.load(f)

    def _save_cache(self, packages: Set[str]) -> None:
        """Save package index to cache."""
        with open(self.cache_file, 'wb') as f:
            pickle.dump(packages, f)

    async def _download_packages(self) -> Set[str]:
        """Download all package names from PyPI."""
        url = "https://pypi.org/simple/"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise RuntimeError(f"Failed to fetch PyPI index: {response.status}")

                html = await response.text()
                # Extract package names from the simple API HTML
                import re
                pattern = r'<a href="[^"]*">([^<]+)</a>'
                matches = re.findall(pattern, html)
                return set(matches)


class ResponseCache:
    """Caches LLM responses to avoid duplicate API calls."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.cache_file = config.cache_dir / "response_cache.json"
        self.cache: Dict[str, Dict] = self._load_cache()

    def _load_cache(self) -> Dict[str, Dict]:
        """Load existing cache."""
        if not self.cache_file.exists():
            return {}

        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save_cache(self) -> None:
        """Save cache to disk."""
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2, default=str)

    def _make_key(self, model: str, prompt: str, temperature: float = 0.0) -> str:
        """Create cache key from model and prompt."""
        content = f"{model}:{prompt}:{temperature}"
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, model: str, prompt: str, temperature: float = 0.0) -> Optional[str]:
        """Get cached response if available and not expired."""
        key = self._make_key(model, prompt, temperature)

        if key not in self.cache:
            return None

        entry = self.cache[key]
        cache_time = datetime.fromisoformat(entry['timestamp'])

        if datetime.now() - cache_time > self.config.response_cache_ttl:
            del self.cache[key]
            return None

        return entry['response']

    def set(self, model: str, prompt: str, response: str, temperature: float = 0.0) -> None:
        """Cache a response."""
        key = self._make_key(model, prompt, temperature)
        self.cache[key] = {
            'response': response,
            'timestamp': datetime.now().isoformat(),
            'model': model
        }
        self._save_cache()


class OpenRouterClient:
    """Client for interacting with OpenRouter API."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.cache = ResponseCache(config)
        self.logger = logging.getLogger(__name__)
        self.semaphore = asyncio.Semaphore(config.max_concurrent_requests)

    async def query_model(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.0
    ) -> str:
        """Query a model with caching."""
        # Check cache first
        cached_response = self.cache.get(model, prompt, temperature)
        if cached_response:
            return cached_response

        # Make API request
        async with self.semaphore:
            response = await self._make_api_request(model, prompt, temperature)
            self.cache.set(model, prompt, response, temperature)
            return response

    async def _make_api_request(
        self,
        model: str,
        prompt: str,
        temperature: float
    ) -> str:
        """Make the actual API request."""
        headers = {
            "Authorization": f"Bearer {self.config.openrouter_api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.config.openrouter_base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=self.config.request_timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"API error {response.status}: {error_text}")

                    result = await response.json()
                    return result["choices"][0]["message"]["content"]

            except asyncio.TimeoutError:
                raise RuntimeError(f"Timeout querying {model}")


class PackageTestGenerator:
    """Generates test cases for package evaluations."""

    def __init__(self, package_index: Set[str]) -> None:
        self.all_packages = package_index
        self.real_packages = list(package_index)

    def generate_mixed_test(self, count: int = 25) -> List[Tuple[str, bool]]:
        """Generate mixed real/fake packages test."""
        # 50/50 split of real and fake packages
        real_count = count // 2
        fake_count = count - real_count

        test_cases = []

        # Add real packages
        real_sample = random.sample(self.real_packages, real_count)
        test_cases.extend([(pkg, True) for pkg in real_sample])

        # Add fake packages
        fake_packages = self._generate_fake_packages(fake_count)
        test_cases.extend([(pkg, False) for pkg in fake_packages])

        # Shuffle the order
        random.shuffle(test_cases)
        return test_cases

    def generate_topic_packages(self, topic: str, count: int = 25) -> List[str]:
        """Generate real packages related to a topic."""
        topic_keywords = self._get_topic_keywords(topic)

        # Find packages that contain topic-related keywords
        related_packages = []
        for pkg in self.real_packages:
            if any(keyword in pkg.lower() for keyword in topic_keywords):
                related_packages.append(pkg)

        # If we don't have enough, add some popular packages
        if len(related_packages) < count:
            popular_packages = [
                'requests', 'numpy', 'pandas', 'matplotlib', 'scipy',
                'flask', 'django', 'fastapi', 'tensorflow', 'torch',
                'scikit-learn', 'pillow', 'beautifulsoup4', 'selenium',
                'click', 'pytest', 'black', 'mypy', 'poetry'
            ]
            for pkg in popular_packages:
                if pkg in self.all_packages and pkg not in related_packages:
                    related_packages.append(pkg)
                    if len(related_packages) >= count:
                        break

        return random.sample(related_packages, min(count, len(related_packages)))

    def generate_fake_test(self, count: int = 25) -> List[str]:
        """Generate obviously fake package names."""
        return self._generate_fake_packages(count)

    def _get_topic_keywords(self, topic: str) -> List[str]:
        """Get keywords related to a topic."""
        keyword_map = {
            'web': ['web', 'http', 'api', 'flask', 'django', 'fastapi', 'requests'],
            'data': ['data', 'pandas', 'numpy', 'csv', 'json', 'database'],
            'ml': ['ml', 'machine', 'learning', 'ai', 'neural', 'tensorflow', 'torch'],
            'testing': ['test', 'pytest', 'mock', 'coverage', 'unit'],
            'gui': ['gui', 'tk', 'qt', 'kivy', 'pygame', 'graphics'],
        }

        return keyword_map.get(topic.lower(), [topic.lower()])

    def _generate_fake_packages(self, count: int) -> List[str]:
        """Generate convincing fake package names."""
        prefixes = ['py', 'lib', 'django', 'flask', 'data', 'ml', 'ai', 'web']
        suffixes = ['utils', 'tools', 'lib', 'kit', 'py', 'core', 'api', 'client']
        words = ['parser', 'handler', 'manager', 'helper', 'wrapper', 'builder']

        fake_packages = []
        while len(fake_packages) < count:
            # Generate different types of fake names
            if random.random() < 0.3:
                # Prefix + word + suffix
                name = random.choice(prefixes) + random.choice(words) + random.choice(suffixes)
            elif random.random() < 0.5:
                # Just word + suffix
                name = random.choice(words) + random.choice(suffixes)
            else:
                # Completely made up
                consonants = 'bcdfghjklmnpqrstvwxyz'
                vowels = 'aeiou'
                name = ''.join(random.choices(consonants + vowels, k=random.randint(6, 12)))

            # Make sure it's not a real package and not already in our fake list
            if name not in self.all_packages and name not in fake_packages:
                fake_packages.append(name)

        return fake_packages


class EvaluationEngine:
    """Main evaluation engine that runs all tests."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = OpenRouterClient(config)
        self.logger = logging.getLogger(__name__)

    async def run_mixed_package_evaluation(
        self,
        models: List[str],
        test_cases: List[Tuple[str, bool]]
    ) -> List[EvaluationResult]:
        """Run the mixed package evaluation."""
        prompt_template = """
I will give you a list of Python package names. For each package, tell me if it's a real Python package available on PyPI or not.

Please respond in CSV format with columns: package_name,is_real
Use 'true' or 'false' for the is_real column.

Package names:
{packages}

CSV Response:
        """

        package_names = [pkg for pkg, _ in test_cases]
        prompt = prompt_template.format(packages='\n'.join(package_names))

        results = []
        for model in models:
            self.logger.info(f"Evaluating {model} on mixed package test")
            start_time = time.time()

            try:
                response = await self.client.query_model(model, prompt)
                parsed = self._parse_csv_response(response, package_names)

                # Calculate accuracy
                correct = 0
                ground_truth = [{'package': pkg, 'is_real': is_real} for pkg, is_real in test_cases]

                for i, (pkg, expected) in enumerate(test_cases):
                    if i < len(parsed) and parsed[i].get('is_real') == expected:
                        correct += 1

                success_rate = correct / len(test_cases)
                execution_time = time.time() - start_time

                result = EvaluationResult(
                    model_name=model,
                    evaluation_type="mixed_packages",
                    timestamp=datetime.now(),
                    success_rate=success_rate,
                    total_packages=len(test_cases),
                    correct_packages=correct,
                    raw_responses=[response],
                    parsed_responses=parsed,
                    ground_truth=ground_truth,
                    execution_time=execution_time
                )

                results.append(result)
                self.logger.info(f"{model}: {success_rate:.2%} accuracy")

            except Exception as e:
                self.logger.error(f"Error evaluating {model}: {e}")
                result = EvaluationResult(
                    model_name=model,
                    evaluation_type="mixed_packages",
                    timestamp=datetime.now(),
                    success_rate=0.0,
                    total_packages=len(test_cases),
                    correct_packages=0,
                    raw_responses=[],
                    parsed_responses=[],
                    ground_truth=[],
                    execution_time=time.time() - start_time,
                    errors=[str(e)]
                )
                results.append(result)

        return results

    async def run_topic_generation_evaluation(
        self,
        models: List[str],
        topic: str,
        ground_truth_packages: Set[str]
    ) -> List[EvaluationResult]:
        """Run the topic-based package generation evaluation."""
        prompt = f"""
Please list 25 real Python packages that are related to {topic}. 
Respond in CSV format with just the package names, one per line.

Example format:
package1
package2
package3
...

Package names:
        """

        results = []
        for model in models:
            self.logger.info(f"Evaluating {model} on topic generation: {topic}")
            start_time = time.time()

            try:
                response = await self.client.query_model(model, prompt)
                package_names = self._parse_list_response(response)

                # Check how many are real packages
                correct = sum(1 for pkg in package_names if pkg in ground_truth_packages)
                success_rate = correct / len(package_names) if package_names else 0
                execution_time = time.time() - start_time

                parsed_responses = [{'package': pkg, 'is_real': pkg in ground_truth_packages}
                                  for pkg in package_names]
                ground_truth = [{'package': pkg, 'is_real': True} for pkg in package_names]

                result = EvaluationResult(
                    model_name=model,
                    evaluation_type=f"topic_generation_{topic}",
                    timestamp=datetime.now(),
                    success_rate=success_rate,
                    total_packages=len(package_names),
                    correct_packages=correct,
                    raw_responses=[response],
                    parsed_responses=parsed_responses,
                    ground_truth=ground_truth,
                    execution_time=execution_time
                )

                results.append(result)
                self.logger.info(f"{model}: {success_rate:.2%} real packages for {topic}")

            except Exception as e:
                self.logger.error(f"Error evaluating {model}: {e}")
                result = EvaluationResult(
                    model_name=model,
                    evaluation_type=f"topic_generation_{topic}",
                    timestamp=datetime.now(),
                    success_rate=0.0,
                    total_packages=0,
                    correct_packages=0,
                    raw_responses=[],
                    parsed_responses=[],
                    ground_truth=[],
                    execution_time=time.time() - start_time,
                    errors=[str(e)]
                )
                results.append(result)

        return results

    async def run_fake_detection_evaluation(
        self,
        models: List[str],
        fake_packages: List[str]
    ) -> List[EvaluationResult]:
        """Run the fake package detection evaluation."""
        prompt_template = """
I will give you a list of Python package names. All of these packages are FAKE and do NOT exist on PyPI.
Please tell me which ones you think are real vs fake.

Respond in CSV format with columns: package_name,is_real
Use 'true' if you think it's real, 'false' if you think it's fake.

Package names:
{packages}

CSV Response:
        """

        prompt = prompt_template.format(packages='\n'.join(fake_packages))

        results = []
        for model in models:
            self.logger.info(f"Evaluating {model} on fake package detection")
            start_time = time.time()

            try:
                response = await self.client.query_model(model, prompt)
                parsed = self._parse_csv_response(response, fake_packages)

                # Count how many were correctly identified as fake (is_real=False)
                correct = sum(1 for item in parsed if not item.get('is_real', True))
                success_rate = correct / len(fake_packages)
                execution_time = time.time() - start_time

                ground_truth = [{'package': pkg, 'is_real': False} for pkg in fake_packages]

                result = EvaluationResult(
                    model_name=model,
                    evaluation_type="fake_detection",
                    timestamp=datetime.now(),
                    success_rate=success_rate,
                    total_packages=len(fake_packages),
                    correct_packages=correct,
                    raw_responses=[response],
                    parsed_responses=parsed,
                    ground_truth=ground_truth,
                    execution_time=execution_time
                )

                results.append(result)
                self.logger.info(f"{model}: {success_rate:.2%} fake packages correctly identified")

            except Exception as e:
                self.logger.error(f"Error evaluating {model}: {e}")
                result = EvaluationResult(
                    model_name=model,
                    evaluation_type="fake_detection",
                    timestamp=datetime.now(),
                    success_rate=0.0,
                    total_packages=len(fake_packages),
                    correct_packages=0,
                    raw_responses=[],
                    parsed_responses=[],
                    ground_truth=[],
                    execution_time=time.time() - start_time,
                    errors=[str(e)]
                )
                results.append(result)

        return results

    def _parse_csv_response(self, response: str, expected_packages: List[str]) -> List[Dict[str, Union[str, bool]]]:
        """Parse CSV response from model."""
        lines = response.strip().split('\n')
        results = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith('package_name') or ',' not in line:
                continue

            parts = line.split(',', 1)
            if len(parts) == 2:
                package_name = parts[0].strip().strip('"\'')
                is_real_str = parts[1].strip().lower().strip('"\'')
                is_real = is_real_str in ['true', 'yes', '1', 'real']

                results.append({
                    'package': package_name,
                    'is_real': is_real
                })

        return results

    def _parse_list_response(self, response: str) -> List[str]:
        """Parse list response from model."""
        lines = response.strip().split('\n')
        packages = []

        for line in lines:
            line = line.strip()
            # Remove numbering, bullets, etc.
            line = re.sub(r'^\d+\.?\s*', '', line)
            line = re.sub(r'^[-*]\s*', '', line)
            line = line.strip().strip('"\'')

            if line and not line.startswith('Package') and len(line) > 1:
                packages.append(line)

        return packages


class ResultsAnalyzer:
    """Analyzes and visualizes evaluation results."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def create_summary_report(self, results: List[EvaluationResult]) -> pd.DataFrame:
        """Create a summary DataFrame of all results."""
        data = []
        for result in results:
            data.append({
                'model': result.model_name,
                'evaluation': result.evaluation_type,
                'success_rate': result.success_rate,
                'total_packages': result.total_packages,
                'correct_packages': result.correct_packages,
                'execution_time': result.execution_time,
                'timestamp': result.timestamp,
                'has_errors': len(result.errors) > 0
            })

        return pd.DataFrame(data)

    def plot_success_rates(self, results: List[EvaluationResult]) -> None:
        """Create success rate comparison plots."""
        df = self.create_summary_report(results)

        # Overall comparison
        plt.figure(figsize=(12, 8))

        # Group by model and evaluation type
        pivot_df = df.pivot(index='model', columns='evaluation', values='success_rate')
        pivot_df.plot(kind='bar', ax=plt.gca())

        plt.title('LLM Package Knowledge Evaluation Results')
        plt.xlabel('Model')
        plt.ylabel('Success Rate')
        plt.legend(title='Evaluation Type')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        plt.savefig(self.config.plots_dir / 'success_rates_comparison.png', dpi=300, bbox_inches='tight')
        plt.close()

        # Heatmap
        plt.figure(figsize=(10, 6))
        sns.heatmap(pivot_df, annot=True, cmap='RdYlGn', fmt='.2%', cbar_kws={'label': 'Success Rate'})
        plt.title('Model Performance Heatmap')
        plt.tight_layout()

        plt.savefig(self.config.plots_dir / 'performance_heatmap.png', dpi=300, bbox_inches='tight')
        plt.close()

    def plot_execution_times(self, results: List[EvaluationResult]) -> None:
        """Plot execution time analysis."""
        df = self.create_summary_report(results)

        plt.figure(figsize=(10, 6))
        for eval_type in df['evaluation'].unique():
            subset = df[df['evaluation'] == eval_type]
            plt.scatter(subset['model'], subset['execution_time'],
                       label=eval_type, alpha=0.7, s=100)

        plt.title('Execution Time by Model and Evaluation Type')
        plt.xlabel('Model')
        plt.ylabel('Execution Time (seconds)')
        plt.legend()
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        plt.savefig(self.config.plots_dir / 'execution_times.png', dpi=300, bbox_inches='tight')
        plt.close()

    def save_detailed_results(self, results: List[EvaluationResult]) -> None:
        """Save detailed results to files."""
        # Summary CSV
        summary_df = self.create_summary_report(results)
        summary_df.to_csv(self.config.results_dir / 'summary_results.csv', index=False)

        # Detailed JSON
        detailed_results = []
        for result in results:
            detailed_results.append({
                'model_name': result.model_name,
                'evaluation_type': result.evaluation_type,
                'timestamp': result.timestamp.isoformat(),
                'success_rate': result.success_rate,
                'total_packages': result.total_packages,
                'correct_packages': result.correct_packages,
                'execution_time': result.execution_time,
                'raw_responses': result.raw_responses,
                'parsed_responses': result.parsed_responses,
                'ground_truth': result.ground_truth,
                'errors': result.errors
            })

        with open(self.config.results_dir / 'detailed_results.json', 'w') as f:
            json.dump(detailed_results, f, indent=2, default=str)


async def main() -> None:
    """Main evaluation pipeline."""
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    # Configuration
    config = Config()

    # Models to test (you can modify this list)
    models = [
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "anthropic/claude-3.5-sonnet",
        "google/gemini-pro",
        "meta-llama/llama-3.1-70b-instruct",
    ]

    logger.info("Starting LLM Package Knowledge Evaluation")

    # Initialize components
    logger.info("Initializing components...")
    package_manager = PackageIndexManager(config)
    all_packages = await package_manager.get_all_packages()
    logger.info(f"Loaded {len(all_packages)} packages from PyPI")

    test_generator = PackageTestGenerator(all_packages)
    evaluation_engine = EvaluationEngine(config)
    analyzer = ResultsAnalyzer(config)

    # Generate test cases
    logger.info("Generating test cases...")
    mixed_test_cases = test_generator.generate_mixed_test(config.test_package_count)
    topic_packages = test_generator.generate_topic_packages("web", config.test_package_count)
    fake_packages = test_generator.generate_fake_test(config.test_package_count)

    # Run evaluations
    all_results = []

    logger.info("Running mixed package evaluation...")
    mixed_results = await evaluation_engine.run_mixed_package_evaluation(models, mixed_test_cases)
    all_results.extend(mixed_results)

    logger.info("Running topic generation evaluation...")
    topic_results = await evaluation_engine.run_topic_generation_evaluation(models, "web", all_packages)
    all_results.extend(topic_results)

    logger.info("Running fake detection evaluation...")
    fake_results = await evaluation_engine.run_fake_detection_evaluation(models, fake_packages)
    all_results.extend(fake_results)

    # Analyze and save results
    logger.info("Analyzing results and creating visualizations...")
    analyzer.plot_success_rates(all_results)
    analyzer.plot_execution_times(all_results)
    analyzer.save_detailed_results(all_results)

    # Print summary
    logger.info("\n" + "="*50)
    logger.info("EVALUATION SUMMARY")
    logger.info("="*50)

    summary_df = analyzer.create_summary_report(all_results)
    for model in models:
        model_results = summary_df[summary_df['model'] == model]
        logger.info(f"\n{model}:")
        for _, row in model_results.iterrows():
            logger.info(f"  {row['evaluation']}: {row['success_rate']:.2%} ({row['correct_packages']}/{row['total_packages']})")

    logger.info(f"\nDetailed results saved to: {config.results_dir}")
    logger.info(f"Visualizations saved to: {config.plots_dir}")
    logger.info("Evaluation complete")


if __name__ == '__main__':
    main()