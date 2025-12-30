"""
Main pipeline for CivicWatch map-reduce summarization.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add civicwatch directory to path for imports
_civicwatch_dir = Path(__file__).parent
if str(_civicwatch_dir) not in sys.path:
    sys.path.insert(0, str(_civicwatch_dir.parent))

from civicwatch.chunker.chunk_text import TextChunker
from civicwatch.config.settings import LOG_LEVEL
from civicwatch.normalizer.normalize import Normalizer
from civicwatch.scraper.base import BaseScraper
from civicwatch.scraper.congress_scraper import CongressScraper
from civicwatch.summarizer.map_summarize import MapSummarizer
from civicwatch.summarizer.reduce_summarize import ReduceSummarizer

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SummarizationPipeline:
    """
    Main pipeline orchestrator for map-reduce summarization.
    """
    
    def __init__(
        self,
        scraper: BaseScraper,
        normalizer: Optional[Normalizer] = None,
        chunker: Optional[TextChunker] = None,
        map_summarizer: Optional[MapSummarizer] = None,
        reduce_summarizer: Optional[ReduceSummarizer] = None
    ):
        """
        Initialize pipeline.
        
        Args:
            scraper: Scraper instance
            normalizer: Normalizer instance (default: new instance)
            chunker: TextChunker instance (default: new instance)
            map_summarizer: MapSummarizer instance (default: new instance)
            reduce_summarizer: ReduceSummarizer instance (default: new instance)
        """
        self.scraper = scraper
        self.normalizer = normalizer or Normalizer()
        self.chunker = chunker or TextChunker()
        self.map_summarizer = map_summarizer or MapSummarizer()
        self.reduce_summarizer = reduce_summarizer or ReduceSummarizer()
    
    def run(self, force_rerun: bool = False) -> Optional[str]:
        """
        Run the complete pipeline.
        
        Args:
            force_rerun: If True, regenerate summaries even if cached
            
        Returns:
            Final summary text or None if error
        """
        logger.info("Starting summarization pipeline...")
        
        try:
            # Step 1: Scrape
            logger.info("Step 1: Scraping...")
            raw_data = self.scraper.scrape()
            logger.info(f"Scraped: {raw_data.get('title', 'Unknown')}")
            
            # Step 2: Normalize
            logger.info("Step 2: Normalizing...")
            source_type = raw_data.get("source_type", "unknown")
            normalized = self.normalizer.normalize(raw_data, source_type)
            doc_id = normalized["id"]
            logger.info(f"Normalized document: {doc_id}")
            
            # Step 3: Chunk
            logger.info("Step 3: Chunking...")
            text = normalized["text"]
            chunks = self.chunker.chunk(doc_id, text)
            logger.info(f"Created {len(chunks)} chunks")
            
            if not chunks:
                logger.warning("No chunks created, cannot summarize")
                return None
            
            # Step 4: Map summarize
            logger.info("Step 4: Map summarizing chunks...")
            chunk_summaries = self.map_summarizer.summarize_chunks(chunks, force_rerun=force_rerun)
            
            if not chunk_summaries:
                logger.warning("No chunk summaries generated")
                return None
            
            # Extract summary texts
            summary_texts = [s["summary"] for s in chunk_summaries]
            logger.info(f"Generated {len(summary_texts)} chunk summaries")
            
            # Step 5: Reduce summarize
            logger.info("Step 5: Reducing summaries...")
            title = normalized["title"]
            final_summary = self.reduce_summarizer.reduce(
                doc_id, title, summary_texts, force_rerun=force_rerun
            )
            
            if final_summary:
                logger.info("Pipeline completed successfully!")
                return final_summary
            else:
                logger.error("Failed to generate final summary")
                return None
                
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="CivicWatch summarization pipeline")
    parser.add_argument(
        "--url",
        type=str,
        help="URL to scrape (or use --mock for testing)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock data for testing"
    )
    parser.add_argument(
        "--force-rerun",
        action="store_true",
        help="Force regeneration of summaries (ignore cache)"
    )
    parser.add_argument(
        "--scraper",
        type=str,
        default="congress",
        choices=["congress", "base"],
        help="Scraper type to use"
    )
    
    args = parser.parse_args()
    
    # Create scraper
    if args.mock:
        mock_data = {
            "title": "Test Civic Document",
            "date": "2025-01-01",
            "text": "This is a test document about civic matters. It contains important information that citizens should know. The document discusses various policy issues and legislative actions.",
            "source_url": "https://example.com/test",
            "source_type": "test"
        }
        scraper = BaseScraper(mock_data=mock_data)
    elif args.url:
        if args.scraper == "congress":
            scraper = CongressScraper(source_url=args.url)
        else:
            scraper = BaseScraper(source_url=args.url)
    else:
        print("Error: Must provide --url or --mock")
        parser.print_help()
        sys.exit(1)
    
    # Create and run pipeline
    pipeline = SummarizationPipeline(scraper=scraper)
    final_summary = pipeline.run(force_rerun=args.force_rerun)
    
    if final_summary:
        print("\n" + "="*80)
        print("FINAL SUMMARY")
        print("="*80)
        print(final_summary)
        print("="*80)
        return 0
    else:
        print("Pipeline failed. Check logs for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

