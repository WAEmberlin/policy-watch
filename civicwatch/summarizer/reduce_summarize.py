"""
Reduce summarizer: combines chunk summaries into final document summary.
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

from civicwatch.config.settings import REDUCE_SUMMARIES_DIR, OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TEMPERATURE

logger = logging.getLogger(__name__)


class ReduceSummarizer:
    """
    Combines chunk summaries into a final document summary.
    """
    
    def __init__(self, model: str = OLLAMA_MODEL, temperature: float = OLLAMA_TEMPERATURE):
        """
        Initialize reduce summarizer.
        
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
        
        # Prompt template for reducing summaries
        self.prompt_template = PromptTemplate(
            input_variables=["summaries", "title"],
            template="""Create a concise weekly civic summary from these chunk summaries.
Group related items.
Avoid repetition.
Highlight major actions.
Use neutral, plain language.

Document title: {title}

Chunk summaries:
{summaries}

Final summary:"""
        )
    
    def reduce(self, doc_id: str, title: str, chunk_summaries: List[str], force_rerun: bool = False) -> Optional[str]:
        """
        Combine chunk summaries into final summary.
        
        Args:
            doc_id: Document ID
            title: Document title
            chunk_summaries: List of chunk summary texts
            force_rerun: If True, regenerate even if cached
            
        Returns:
            Final summary text or None if error
        """
        if not chunk_summaries:
            return None
        
        # Check cache
        if not force_rerun:
            cached = self._load_cached_summary(doc_id)
            if cached:
                logger.debug(f"Using cached final summary for {doc_id}")
                return cached
        
        # Combine summaries
        summaries_text = "\n\n".join([f"Chunk {i+1}: {s}" for i, s in enumerate(chunk_summaries)])
        
        # Generate final summary
        try:
            prompt = self.prompt_template.format(summaries=summaries_text, title=title)
            
            logger.info(f"Reducing summaries for {doc_id}...")
            final_summary = self.llm.invoke(prompt)
            
            # Clean up
            final_summary = final_summary.strip()
            
            # Save to cache
            self._save_summary(doc_id, final_summary)
            
            return final_summary
            
        except Exception as e:
            logger.error(f"Error reducing summaries for {doc_id}: {e}")
            return None
    
    def _load_cached_summary(self, doc_id: str) -> Optional[str]:
        """
        Load cached final summary if it exists.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Cached summary text or None
        """
        filename = f"{doc_id}_final.json"
        filepath = REDUCE_SUMMARIES_DIR / filename
        
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("summary", "")
            except Exception as e:
                logger.warning(f"Error loading cached summary {filepath}: {e}")
        
        return None
    
    def _save_summary(self, doc_id: str, summary: str) -> None:
        """
        Save final summary to cache.
        
        Args:
            doc_id: Document ID
            summary: Final summary text
        """
        filename = f"{doc_id}_final.json"
        filepath = REDUCE_SUMMARIES_DIR / filename
        
        data = {
            "doc_id": doc_id,
            "summary": summary
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved final summary to {filepath}")

