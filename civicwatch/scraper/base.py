"""
Base scraper class for extracting civic/government data.
"""
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from civicwatch.config.settings import RAW_DIR

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Base class for scrapers that extract civic/government data.
    
    Subclasses should implement extract_content() to parse specific sources.
    """
    
    def __init__(self, source_url: Optional[str] = None, mock_data: Optional[Dict] = None):
        """
        Initialize scraper.
        
        Args:
            source_url: URL to scrape from
            mock_data: Optional mock data for testing (bypasses actual scraping)
        """
        self.source_url = source_url
        self.mock_data = mock_data
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "CivicWatch/1.0 (Civic Transparency Project)"
        })
    
    def scrape(self) -> Dict:
        """
        Main scraping method. Returns normalized dict with:
        - title: str
        - date: str (ISO format if available)
        - text: str (raw text content)
        - source_url: str
        - source_type: str
        
        Returns:
            Dict with scraped data
        """
        if self.mock_data:
            logger.info("Using mock data instead of scraping")
            return self.mock_data
        
        if not self.source_url:
            raise ValueError("Either source_url or mock_data must be provided")
        
        logger.info(f"Scraping: {self.source_url}")
        
        try:
            response = self.session.get(self.source_url, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Extract content using subclass implementation
            data = self.extract_content(soup, self.source_url)
            
            # Save raw data
            self._save_raw(data)
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {self.source_url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error parsing {self.source_url}: {e}")
            raise
    
    @abstractmethod
    def extract_content(self, soup: BeautifulSoup, url: str) -> Dict:
        """
        Extract content from parsed HTML.
        
        Args:
            soup: BeautifulSoup parsed HTML
            url: Source URL
            
        Returns:
            Dict with: title, date (optional), text, source_url, source_type
        """
        pass
    
    def _extract_text(self, soup: BeautifulSoup) -> str:
        """
        Extract clean text from HTML, removing navigation and junk.
        
        Args:
            soup: BeautifulSoup parsed HTML
            
        Returns:
            Clean text content
        """
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = " ".join(chunk for chunk in chunks if chunk)
        
        return text
    
    def _save_raw(self, data: Dict) -> None:
        """
        Save raw scraped data to storage/raw/.
        
        Args:
            data: Scraped data dict
        """
        # Generate filename from URL hash
        url_hash = hashlib.md5(self.source_url.encode()).hexdigest()[:12]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{url_hash}.json"
        filepath = RAW_DIR / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved raw data to {filepath}")

