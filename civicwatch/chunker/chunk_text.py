"""
Text chunker for splitting documents into overlapping chunks.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict

from civicwatch.config.settings import CHUNKS_DIR, CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)


class TextChunker:
    """
    Chunks text into overlapping segments for summarization.
    """
    
    def __init__(self, chunk_size: int = CHUNK_SIZE, overlap: float = CHUNK_OVERLAP):
        """
        Initialize chunker.
        
        Args:
            chunk_size: Target chunk size in characters
            overlap: Overlap ratio (0.0 to 1.0)
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.overlap_size = int(chunk_size * overlap)
    
    def chunk(self, doc_id: str, text: str) -> List[Dict]:
        """
        Chunk text into overlapping segments.
        
        Args:
            doc_id: Parent document ID
            text: Text to chunk
            
        Returns:
            List of chunk dicts with:
            {
                parent_id: str
                chunk_index: int
                text: str
            }
        """
        if not text:
            return []
        
        chunks = []
        
        # Try to preserve paragraph boundaries
        paragraphs = text.split("\n\n")
        
        current_chunk = ""
        chunk_index = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # If adding this paragraph would exceed chunk size
            if len(current_chunk) + len(para) + 2 > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append({
                    "parent_id": doc_id,
                    "chunk_index": chunk_index,
                    "text": current_chunk.strip()
                })
                chunk_index += 1
                
                # Start new chunk with overlap
                if self.overlap_size > 0:
                    # Take last N characters from previous chunk
                    overlap_text = current_chunk[-self.overlap_size:]
                    current_chunk = f"{overlap_text}\n\n{para}"
                else:
                    current_chunk = para
            else:
                # Add paragraph to current chunk
                if current_chunk:
                    current_chunk += f"\n\n{para}"
                else:
                    current_chunk = para
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append({
                "parent_id": doc_id,
                "chunk_index": chunk_index,
                "text": current_chunk.strip()
            })
        
        # If text is shorter than chunk size, ensure we have at least one chunk
        if not chunks and text:
            chunks.append({
                "parent_id": doc_id,
                "chunk_index": 0,
                "text": text.strip()
            })
        
        # Save chunks
        self._save_chunks(doc_id, chunks)
        
        logger.info(f"Chunked document {doc_id} into {len(chunks)} chunks")
        
        return chunks
    
    def _save_chunks(self, doc_id: str, chunks: List[Dict]) -> None:
        """
        Save chunks to storage.
        
        Args:
            doc_id: Parent document ID
            chunks: List of chunk dicts
        """
        filename = f"{doc_id}_chunks.json"
        filepath = CHUNKS_DIR / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved {len(chunks)} chunks to {filepath}")

