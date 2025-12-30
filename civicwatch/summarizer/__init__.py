"""
Summarizer module for map-reduce summarization using Ollama.
"""
from .map_summarize import MapSummarizer
from .reduce_summarize import ReduceSummarizer

__all__ = ["MapSummarizer", "ReduceSummarizer"]

