"""
RAG utilities

1. PDF text extraction
2. Text chunking
3. Embedding creation
4. Prompt building
"""

import time

import fitz
from openai import OpenAI


EMBEDDING_MODEL = "text-embedding-3-small"


def extract_pdf_pages(file_bytes: bytes) -> list[dict]:
    """
    Extract text from each PDF page

    Returns:
    [
      {"page_number": 1, "text": "..."},
      {"page_number": 2, "text": "..."}
    ]
    """

    pages: list[dict] = []

    pdf = fitz.open(stream=file_bytes, filetype="pdf")

    for page_index, page in enumerate(pdf):
        text = page.get_text("text").strip()

        if text:
            pages.append(
                {
                    "page_number": page_index + 1,
                    "text": text,
                }
            )

    return pages


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    """
    Split text into overlapping chunks.

    Because important context may cross chunk boundaries.
    """

    chunks: list[str] = []

    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def create_embedding(    client: OpenAI,
    text: str,
    max_retries: int = 3,
    retry_delay_seconds: float = 1.0,
    ) -> list[float]:
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text,
            )

            return response.data[0].embedding

        except Exception as error:
            last_error = error

            if attempt == max_retries:
                break

            time.sleep(retry_delay_seconds * attempt)

    raise RuntimeError(f"Failed to create embedding after retries: {last_error}")


def build_rag_prompt(question: str, chunks: list[str]) -> str:
    """
    Build prompt using retrieved context.
    """
    
    context_blocks = []

    for chunk in chunks:
        context_blocks.append(
            f"""
        [Source {chunk["source_id"]}]
        Filename: {chunk["filename"]}
        Page: {chunk["page_number"]}
        Content:
        {chunk["content"]}
        """.strip()
                )
        
    context = "\n\n---\n\n".join(context_blocks)

    return f"""
You are an AI assistant answering questions based on the provided document context.

Rules:
- Answer only using the provided context when possible.
- Use citations like [Source 1], [Source 2] when referring to document information.
- If the context does not contain enough information, say you do not have enough information.
- Be concise and accurate.

Context:
{context}

Question:
{question}

Answer:
""".strip()