"""Shared test configuration."""

import os

# Set TESTING env var before any app imports to skip FAISS loading in lifespan
os.environ["TESTING"] = "1"
