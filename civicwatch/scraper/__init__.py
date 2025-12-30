"""
Scraper module for extracting civic/government data from various sources.
"""
from .base import BaseScraper
from .congress_scraper import CongressScraper

__all__ = ["BaseScraper", "CongressScraper"]

