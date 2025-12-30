"""
Example usage of the CivicWatch summarization pipeline.
"""
from civicwatch.pipeline import SummarizationPipeline
from civicwatch.scraper.congress_scraper import CongressScraper

# Example 1: Scrape and summarize a Congress.gov URL
def example_congress_url():
    """Example: Summarize a Congress.gov bill page."""
    url = "https://www.congress.gov/bill/119th-congress/house-bill/1234"
    scraper = CongressScraper(source_url=url)
    pipeline = SummarizationPipeline(scraper=scraper)
    summary = pipeline.run()
    
    if summary:
        print("Summary generated successfully!")
        print(summary)
    else:
        print("Failed to generate summary")

# Example 2: Use mock data for testing
def example_mock_data():
    """Example: Test with mock data."""
    from civicwatch.scraper.base import BaseScraper
    
    mock_data = {
        "title": "Example Bill: Improving Civic Transparency",
        "date": "2025-01-15",
        "text": """
        This bill proposes significant improvements to civic transparency.
        
        Section 1: The bill requires all government agencies to publish
        their meeting minutes within 48 hours of each meeting.
        
        Section 2: Public comment periods must be extended to at least
        30 days for major policy changes.
        
        Section 3: All budget documents must be published in machine-readable
        formats to enable better public analysis.
        
        This legislation aims to increase public trust in government
        by making information more accessible and timely.
        """,
        "source_url": "https://example.com/bill/123",
        "source_type": "congress"
    }
    
    scraper = BaseScraper(mock_data=mock_data)
    pipeline = SummarizationPipeline(scraper=scraper)
    summary = pipeline.run()
    
    if summary:
        print("Mock data summary:")
        print(summary)

if __name__ == "__main__":
    print("CivicWatch Pipeline Examples")
    print("=" * 50)
    
    # Run mock example (doesn't require internet)
    print("\nExample 1: Mock Data")
    example_mock_data()
    
    # Uncomment to run with real URL (requires internet + Ollama)
    # print("\nExample 2: Congress.gov URL")
    # example_congress_url()

