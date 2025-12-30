"""
Congress.gov scraper for extracting bill and hearing information.
"""
import logging
from typing import Dict, Optional

from bs4 import BeautifulSoup

from civicwatch.scraper.base import BaseScraper

logger = logging.getLogger(__name__)


class CongressScraper(BaseScraper):
    """
    Scraper for Congress.gov pages (bills, hearings, etc.).
    """
    
    def extract_content(self, soup: BeautifulSoup, url: str) -> Dict:
        """
        Extract content from Congress.gov page.
        
        Args:
            soup: BeautifulSoup parsed HTML
            url: Source URL
            
        Returns:
            Dict with extracted data
        """
        # Extract title
        title = ""
        title_elem = soup.find("h1") or soup.find("title")
        if title_elem:
            title = title_elem.get_text().strip()
        
        # Extract date (look for common date patterns)
        date_str = None
        date_elem = soup.find(class_=lambda x: x and "date" in x.lower())
        if date_elem:
            date_str = date_elem.get_text().strip()
        
        # Try to find date in meta tags
        if not date_str:
            meta_date = soup.find("meta", property="article:published_time")
            if meta_date:
                date_str = meta_date.get("content", "")
        
        # Extract main content
        # Congress.gov typically has content in specific divs
        main_content = soup.find("div", class_=lambda x: x and ("content" in x.lower() or "main" in x.lower()))
        if not main_content:
            # Fallback: use body text
            main_content = soup.find("body")
        
        if main_content:
            text = self._extract_text(main_content)
        else:
            text = self._extract_text(soup)
        
        return {
            "title": title or "Congressional Document",
            "date": date_str,
            "text": text,
            "source_url": url,
            "source_type": "congress"
        }

