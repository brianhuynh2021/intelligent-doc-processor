

import os
import sys
import time
from typing import List

from openai import OpenAI

# Make sure we can import the app package when running as a script
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings

"""
Simple benchmark script to compare different embedding models.

Usage:
    python scripts/benchmark_embeddings.py
"""


client = OpenAI(api_key=settings.OPENAI_API_KEY)

# List of embedding models to benchmark
MODELS: List[str] = [
    "text-embedding-3-small",
    # Uncomment this if you want to compare with the larger model as well
    # "text-embedding-3-large",
]

# Sample texts for the benchmark
TEXTS = [
    "FastAPI is a modern, high-performance web framework for building APIs with Python.",
    "Qdrant is a vector database designed for storing and searching embeddings.",
    "Redis can be used as a cache layer to speed up repeated computations.",
    "Embeddings map text into high-dimensional vectors for semantic search.",
    "OpenAI provides state-of-the-art models for both generation and embeddings.",
]* 10  # 50 texts total


def bench_model(model: str) -> None:
    print(f"\n=== Benchmarking model: {model} ===")
    t0 = time.perf_counter()
    response = client.embeddings.create(
        model=model,
        input=TEXTS,
    )
    t1 = time.perf_counter()

    dim = len(response.data[0].embedding)
    total_time = t1 - t0

    print(f"Vectors: {len(TEXTS)}")
    print(f"Dimension: {dim}")
    print(f"Total time: {total_time:.3f} seconds")
    print(f"Avg per text: {total_time / len(TEXTS):.4f} seconds")


def main() -> None:
    for model in MODELS:
        bench_model(model)


if __name__ == "__main__":
    main()