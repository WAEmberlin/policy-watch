"""
Normalizer for converting scraper output into a clean, standardized schema.
"""
import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from civicwatch.config.settings import NORMALIZED_DIR

logger = logging.getLogger(__name__)


class Normalizer:
    """
    Normalizes scraped data into a clean schema.
    """
    
    def __init__(self):
        """Initialize normalizer."""
        pass
    
    def normalize(self, raw_data: Dict, source_type: str = "unknown") -> Dict:
        """
        Normalize raw scraped data into clean schema.
        
        Args:
            raw_data: Raw data from scraper
            source_type: Type of source (congress, kansas, etc.)
            
        Returns:
            Normalized dict with schema:
            {
                id: str (hash-based unique ID)
                source: str
                title: str
                date: str (ISO format)
                text: str (cleaned)
                chamber: str (optional)
                committee: str (optional)
                tags: List[str]
            }
        """
        # Extract and clean fields
        title = self._clean_text(raw_data.get("title", ""))
        text = self._clean_text(raw_data.get("text", ""))
        source_url = raw_data.get("source_url", "")
        date_str = raw_data.get("date", "")
        
        # Parse and normalize date
        normalized_date = self._normalize_date(date_str)
        
        # Extract chamber and committee from text/title
        chamber = self._extract_chamber(title, text)
        committee = self._extract_committee(title, text)
        
        # Generate tags
        tags = self._generate_tags(title, text, source_type)
        
        # Generate unique ID
        doc_id = self._generate_id(source_url, title, normalized_date)
        
        # Build normalized document
        normalized = {
            "id": doc_id,
            "source": source_type,
            "title": title,
            "date": normalized_date,
            "text": text,
            "chamber": chamber,
            "committee": committee,
            "tags": tags,
            "source_url": source_url,
            "normalized_at": datetime.now().isoformat()
        }
        
        # Save to storage
        self._save_normalized(normalized)
        
        return normalized
    
    def _clean_text(self, text: str) -> str:
        """
        Clean text: remove extra whitespace, normalize line breaks.
        
        Args:
            text: Raw text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def _normalize_date(self, date_str: Optional[str]) -> str:
        """
        Normalize date string to ISO format.
        
        Args:
            date_str: Date string in various formats
            
        Returns:
            ISO format date string (YYYY-MM-DD) or empty string
        """
        if not date_str:
            return ""
        
        # Try parsing common formats
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%B %d, %Y",
            "%b %d, %Y",
            "%m/%d/%Y",
            "%d/%m/%Y"
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.date().isoformat()
            except ValueError:
                continue
        
        # If all parsing fails, return empty
        logger.warning(f"Could not parse date: {date_str}")
        return ""
    
    def _extract_chamber(self, title: str, text: str) -> str:
        """
        Extract chamber (House/Senate) from title or text.
        
        Args:
            title: Document title
            text: Document text
            
        Returns:
            Chamber name or empty string
        """
        combined = f"{title} {text}".lower()
        
        if "house" in combined and "senate" not in combined:
            return "House"
        elif "senate" in combined:
            return "Senate"
        
        return ""
    
    def _extract_committee(self, title: str, text: str) -> str:
        """
        Extract committee name from title or text.
        
        Args:
            title: Document title
            text: Document text
            
        Returns:
            Committee name or empty string
        """
        combined = f"{title} {text}"
        
        # Look for "Committee" or "Subcommittee" patterns
        pattern = r'([A-Z][a-zA-Z\s]+(?:Committee|Subcommittee))'
        matches = re.findall(pattern, combined)
        
        if matches:
            # Return first match, cleaned
            return matches[0].strip()
        
        return ""
    
    def _generate_tags(self, title: str, text: str, source_type: str) -> List[str]:
        """
        Generate tags based on content.
        
        Args:
            title: Document title
            text: Document text
            source_type: Source type
            
        Returns:
            List of tag strings
        """
        tags = [source_type]
        
        combined = f"{title} {text}".lower()
        
        # Common civic/government keywords
        keyword_map = {
            "budget": "budget",
            "appropriation": "budget",
            "health": "healthcare",
            "healthcare": "healthcare",
            "education": "education",
            "environment": "environment",
            "climate": "environment",
            "energy": "energy",
            "defense": "defense",
            "veteran": "veterans",
            "immigration": "immigration",
            "tax": "taxation",
            "infrastructure": "infrastructure",
            "transportation": "infrastructure",
            "hearing": "hearing",
            "bill": "legislation",
            "act": "legislation"
        }
        
        for keyword, tag in keyword_map.items():
            if keyword in combined and tag not in tags:
                tags.append(tag)
        
        return tags
    
    def _generate_id(self, source_url: str, title: str, date: str) -> str:
        """
        Generate unique ID for document.
        
        Args:
            source_url: Source URL
            title: Document title
            date: Document date
            
        Returns:
            Unique ID string
        """
        # Create hash from URL + title + date
        content = f"{source_url}|{title}|{date}"
        doc_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        return f"doc_{doc_hash}"
    
    def _save_normalized(self, normalized: Dict) -> None:
        """
        Save normalized document to storage.
        
        Args:
            normalized: Normalized document dict
        """
        doc_id = normalized["id"]
        filename = f"{doc_id}.json"
        filepath = NORMALIZED_DIR / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(normalized, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved normalized document: {filepath}")

