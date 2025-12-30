# CivicWatch Map-Reduce Summarization Pipeline

A local, free, map-reduce summarization pipeline for civic transparency data. Uses Ollama for local LLM inference - no paid APIs required.

## ⚠️ Important: Deployment Strategy

**This pipeline requires Ollama running locally with GPU access.** Since your website runs on GitHub Actions (cloud, no GPU), we use a **hybrid approach**:

1. **Base summaries** (always work): The existing `weekly_overview.py` generates simple summaries that work everywhere
2. **Enhanced summaries** (optional): This pipeline enhances summaries when Ollama is available
3. **Caching**: Pre-generated summaries can be committed to the repo for use when Ollama is offline

**See [DEPLOYMENT.md](DEPLOYMENT.md) for full deployment guide.**

**Quick answer**: Run this locally when your laptop is on, commit the results, and the website will use cached summaries even when your laptop is off.

## Features

- **Local Processing**: Runs entirely on your machine using Ollama
- **Map-Reduce Architecture**: Chunks documents, summarizes chunks independently, then combines
- **Caching**: Skips re-summarization of existing chunks (unless `--force-rerun`)
- **Extensible**: Easy to add new scrapers and normalizers
- **Clean Schema**: Normalized data structure for consistent processing

## Requirements

- Python 3.10+
- Ollama running locally at `http://localhost:11434`
- Ollama model installed (default: `llama3.1:8b`)
- Required Python packages (see Installation)

## Installation

1. **Install Ollama** (if not already installed):
   ```bash
   # Visit https://ollama.ai and download for your OS
   # Or use: curl -fsSL https://ollama.ai/install.sh | sh
   ```

2. **Pull the model**:
   ```bash
   ollama pull llama3.1:8b
   ```

3. **Install Python dependencies**:
   ```bash
   pip install langchain langchain-community beautifulsoup4 requests
   ```

## Project Structure

```
civicwatch/
├── config/
│   └── settings.py          # Configuration (Ollama URL, model, chunking params)
├── scraper/
│   ├── base.py              # Base scraper class
│   └── congress_scraper.py  # Congress.gov scraper
├── normalizer/
│   └── normalize.py         # Schema normalization
├── chunker/
│   └── chunk_text.py        # Text chunking with overlap
├── summarizer/
│   ├── map_summarize.py     # Chunk-level summarization
│   └── reduce_summarize.py  # Final summary generation
├── storage/
│   ├── raw/                 # Raw scraped data
│   ├── normalized/         # Normalized documents
│   ├── chunks/              # Text chunks
│   └── summaries/           # Generated summaries
│       ├── map/             # Chunk summaries
│       └── reduce/          # Final summaries
├── pipeline.py              # Main orchestrator
└── README.md
```

## Usage

### Basic Usage

Scrape and summarize a URL:
```bash
python civicwatch/pipeline.py --url "https://www.congress.gov/bill/119th-congress/house-bill/1234"
```

### With Mock Data (Testing)

Test without scraping:
```bash
python civicwatch/pipeline.py --mock
```

### Force Regeneration

Regenerate summaries even if cached:
```bash
python civicwatch/pipeline.py --url "https://..." --force-rerun
```

### Different Scrapers

Use Congress scraper (default):
```bash
python civicwatch/pipeline.py --url "https://..." --scraper congress
```

## Configuration

Edit `civicwatch/config/settings.py` or set environment variables:

```bash
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="llama3.1:8b"
export OLLAMA_TEMPERATURE="0.2"
export CHUNK_SIZE="1000"
export CHUNK_OVERLAP="0.15"
export LOG_LEVEL="INFO"
```

## How It Works

1. **Scrape**: Extracts title, date, text from source URL
2. **Normalize**: Converts to clean schema with ID, tags, chamber, committee
3. **Chunk**: Splits text into overlapping chunks (~1000 chars, 15% overlap)
4. **Map Summarize**: Each chunk summarized independently using Ollama
5. **Reduce Summarize**: Chunk summaries combined into final document summary

## Output

The pipeline generates:

- **Raw data**: `storage/raw/` - Original scraped content
- **Normalized docs**: `storage/normalized/` - Clean schema JSON
- **Chunks**: `storage/chunks/` - Text chunks per document
- **Chunk summaries**: `storage/summaries/map/` - Individual chunk summaries
- **Final summaries**: `storage/summaries/reduce/` - Combined summaries

## Extending

### Add a New Scraper

Create `civicwatch/scraper/my_scraper.py`:

```python
from civicwatch.scraper.base import BaseScraper
from bs4 import BeautifulSoup

class MyScraper(BaseScraper):
    def extract_content(self, soup: BeautifulSoup, url: str) -> Dict:
        # Your extraction logic
        return {
            "title": "...",
            "date": "...",
            "text": "...",
            "source_url": url,
            "source_type": "my_source"
        }
```

### Customize Normalization

Edit `civicwatch/normalizer/normalize.py` to add:
- Custom tag generation
- Additional field extraction
- Source-specific parsing

## Troubleshooting

**Ollama connection error**:
- Ensure Ollama is running: `ollama serve`
- Check `OLLAMA_BASE_URL` in settings

**Model not found**:
- Pull the model: `ollama pull llama3.1:8b`
- Or change `OLLAMA_MODEL` to an installed model

**Out of memory**:
- Use a smaller model: `llama3.1:3b`
- Reduce `CHUNK_SIZE`

**Slow processing**:
- Normal for large documents
- Caching speeds up subsequent runs
- Consider GPU acceleration (Ollama uses GPU automatically if available)

## License

Part of the CivicWatch civic transparency project.

