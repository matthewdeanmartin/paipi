#!/usr/bin/env python3
"""
Quick runner script for the LLM Package Knowledge Evaluator.

Usage:
    python run_evaluation.py --config config.json
    python run_evaluation.py --models gpt-4o claude-3.5-sonnet --topics web ml
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

# Import from the main evaluation module
from pypi_bench.main import (
    Config,
    PackageIndexManager,
    PackageTestGenerator,
    EvaluationEngine,
    ResultsAnalyzer
)


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from file or use defaults."""
    config = Config()

    if config_path and Path(config_path).exists():
        with open(config_path, 'r') as f:
            config_data = json.load(f)

        # Update config with loaded values
        if 'openrouter_api_key' in config_data:
            config.openrouter_api_key = config_data['openrouter_api_key']

        if 'evaluation_settings' in config_data:
            settings = config_data['evaluation_settings']
            if 'test_package_count' in settings:
                config.test_package_count = settings['test_package_count']
            if 'max_concurrent_requests' in settings:
                config.max_concurrent_requests = settings['max_concurrent_requests']
            if 'request_timeout' in settings:
                config.request_timeout = settings['request_timeout']

    return config


async def run_quick_evaluation(
        models: List[str],
        topics: List[str] = None,
        config: Optional[Config] = None
) -> None:
    """Run a quick evaluation with specified parameters."""
    if config is None:
        config = Config()

    if topics is None:
        topics = ["web"]

    logger = logging.getLogger(__name__)
    logger.info(f"Running evaluation for models: {', '.join(models)}")
    logger.info(f"Topics: {', '.join(topics)}")

    # Initialize components
    package_manager = PackageIndexManager(config)
    all_packages = await package_manager.get_all_packages()
    logger.info(f"Loaded {len(all_packages)} packages from PyPI")

    test_generator = PackageTestGenerator(all_packages)
    evaluation_engine = EvaluationEngine(config)
    analyzer = ResultsAnalyzer(config)

    all_results = []

    # Run mixed package evaluation
    logger.info("Running mixed package evaluation...")
    mixed_test_cases = test_generator.generate_mixed_test(config.test_package_count)
    mixed_results = await evaluation_engine.run_mixed_package_evaluation(models, mixed_test_cases)
    all_results.extend(mixed_results)

    # Run topic evaluations
    for topic in topics:
        logger.info(f"Running topic evaluation for: {topic}")
        topic_results = await evaluation_engine.run_topic_generation_evaluation(models, topic, all_packages)
        all_results.extend(topic_results)

    # Run fake detection
    logger.info("Running fake package detection...")
    fake_packages = test_generator.generate_fake_test(config.test_package_count)
    fake_results = await evaluation_engine.run_fake_detection_evaluation(models, fake_packages)
    all_results.extend(fake_results)

    # Analyze results
    logger.info("Creating visualizations...")
    analyzer.plot_success_rates(all_results)
    analyzer.plot_execution_times(all_results)
    analyzer.save_detailed_results(all_results)

    # Print quick summary
    print("\n" + "=" * 60)
    print("QUICK EVALUATION SUMMARY")
    print("=" * 60)

    summary_df = analyzer.create_summary_report(all_results)

    # Group by model and show average performance
    for model in models:
        model_results = summary_df[summary_df['model'] == model]
        avg_success = model_results['success_rate'].mean()
        print(f"\n{model}: {avg_success:.2%} average success rate")

        for _, row in model_results.iterrows():
            print(f"  • {row['evaluation']}: {row['success_rate']:.2%}")

    print(f"\nResults saved to: {config.results_dir}")
    print(f"Plots saved to: {config.plots_dir}")


def main() -> None:
    """Command line interface."""
    parser = argparse.ArgumentParser(description="LLM Package Knowledge Evaluator")

    parser.add_argument(
        '--config', '-c',
        type=str,
        help="Path to configuration JSON file"
    )

    parser.add_argument(
        '--models', '-m',
        nargs='+',
        default=["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"],
        help="Models to evaluate"
    )

    parser.add_argument(
        '--topics', '-t',
        nargs='+',
        default=["web"],
        help="Topics for generation evaluation"
    )

    parser.add_argument(
        '--api-key',
        type=str,
        help="OpenRouter API key (overrides config file)"
    )

    parser.add_argument(
        '--quick',
        action='store_true',
        help="Run a quick evaluation with fewer packages"
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Load configuration
    config = load_config(args.config)

    # Override with command line arguments
    if args.api_key:
        config.openrouter_api_key = args.api_key

    if args.quick:
        config.test_package_count = 10
        config.max_concurrent_requests = 3

    # Validate API key
    if not config.openrouter_api_key or config.openrouter_api_key == "your-openrouter-api-key-here":
        print("ERROR: Please set your OpenRouter API key!")
        print("Either use --api-key or set it in the config file.")
        sys.exit(1)

    # Run evaluation
    try:
        asyncio.run(run_quick_evaluation(args.models, args.topics, config))
    except KeyboardInterrupt:
        print("\nEvaluation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()