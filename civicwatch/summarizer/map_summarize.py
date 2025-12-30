"""
Map summarizer: summarizes individual chunks using Ollama.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

try:
    from langchain_community.llms import Ollama
    from langchain.prompts import PromptTemplate
except ImportError:
    # Fallback for older LangChain versions
    try:
        from langchain.llms import Ollama
        from langchain import PromptTemplate
    except ImportError:
        raise ImportError(
            "LangChain not installed. Install with: pip install langchain langchain-community"
        )

from civicwatch.config.settings import MAP_SUMMARIES_DIR, OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TEMPERATURE

logger = logging.getLogger(__name__)


class MapSummarizer:
    """
    Summarizes individual text chunks using Ollama.
    """
    
    def __init__(self, model: str = OLLAMA_MODEL, temperature: float = OLLAMA_TEMPERATURE):
        """
        Initialize map summarizer.
        
        Args:
            model: Ollama model name
            temperature: Temperature for generation
        """
        self.model = model
        self.temperature = temperature
        self.llm = Ollama(
            base_url=OLLAMA_BASE_URL,
            model=model,
            temperature=temperature
        )
        
        # Prompt template for chunk summarization
        self.prompt_template = PromptTemplate(
            input_variables=["text"],
            template="""Summarize this civic or government-related text in 2-3 sentences.
Focus on actions taken and why it matters to the public.
Use neutral tone.

Text to summarize:
{text}

Summary:"""
        )
    
    def summarize_chunk(self, chunk: Dict, force_rerun: bool = False) -> Optional[str]:
        """
        Summarize a single chunk.
        
        Args:
            chunk: Chunk dict with parent_id, chunk_index, text
            force_rerun: If True, regenerate even if cached
            
        Returns:
            Summary text or None if error
        """
        parent_id = chunk["parent_id"]
        chunk_index = chunk["chunk_index"]
        
        # Check cache
        if not force_rerun:
            cached = self._load_cached_summary(parent_id, chunk_index)
            if cached:
                logger.debug(f"Using cached summary for {parent_id} chunk {chunk_index}")
                return cached
        
        # Generate summary
        try:
            text = chunk["text"]
            prompt = self.prompt_template.format(text=text)
            
            logger.info(f"Summarizing chunk {chunk_index} of {parent_id}...")
            summary = self.llm.invoke(prompt)
            
            # Clean up summary
            summary = summary.strip()
            
            # Save to cache
            self._save_summary(parent_id, chunk_index, summary)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error summarizing chunk {parent_id}/{chunk_index}: {e}")
            return None
    
    def summarize_chunks(self, chunks: List[Dict], force_rerun: bool = False) -> List[Dict]:
        """
        Summarize multiple chunks.
        
        Args:
            chunks: List of chunk dicts
            force_rerun: If True, regenerate even if cached
            
        Returns:
            List of dicts with parent_id, chunk_index, summary
        """
        summaries = []
        
        for chunk in chunks:
            summary_text = self.summarize_chunk(chunk, force_rerun=force_rerun)
            if summary_text:
                summaries.append({
                    "parent_id": chunk["parent_id"],
                    "chunk_index": chunk["chunk_index"],
                    "summary": summary_text
                })
        
        return summaries
    
    def _load_cached_summary(self, parent_id: str, chunk_index: int) -> Optional[str]:
        """
        Load cached summary if it exists.
        
        Args:
            parent_id: Parent document ID
            chunk_index: Chunk index
            
        Returns:
            Cached summary text or None
        """
        filename = f"{parent_id}_chunk_{chunk_index}.json"
        filepath = MAP_SUMMARIES_DIR / filename
        
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("summary", "")
            except Exception as e:
                logger.warning(f"Error loading cached summary {filepath}: {e}")
        
        return None
    
    def _save_summary(self, parent_id: str, chunk_index: int, summary: str) -> None:
        """
        Save summary to cache.
        
        Args:
            parent_id: Parent document ID
            chunk_index: Chunk index
            summary: Summary text
        """
        filename = f"{parent_id}_chunk_{chunk_index}.json"
        filepath = MAP_SUMMARIES_DIR / filename
        
        data = {
            "parent_id": parent_id,
            "chunk_index": chunk_index,
            "summary": summary
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved summary to {filepath}")

