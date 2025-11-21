import re
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter

DEFAULT_CHUNK_SIZE = 1000  # ~ 250 tokens
DEFAULT_CHUNK_OVERLAP = 200  # ~ 20% overlap


def clean_text(raw_text: str) -> str:
    """
    Làm sạch text trước khi chunk:
    - bỏ \r
    - gom nhiều newline liên tiếp
    - gom nhiều space/tabs liên tiếp
    """
    if not raw_text:
        return ""

    text = raw_text.replace("\r", "\n")
    # gom nhiều dòng trống
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    # gom nhiều space/tab
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def split_text_into_chunks(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[str]:
    """
    Dùng RecursiveCharacterTextSplitter để cắt text thành nhiều chunk.
    Trả về list các đoạn string (không chứa metadata).
    """
    cleaned = clean_text(text)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = splitter.split_text(cleaned)
    return chunks


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
):
    """
    Split text into chunks and also return (start_index, end_index) for each chunk.
    Output format: List[(chunk_content, start_idx, end_idx)]
    """
    cleaned = clean_text(text)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = splitter.split_text(cleaned)

    result = []
    search_pos = 0
    for chunk in chunks:
        start = cleaned.find(chunk, search_pos)
        if start == -1:
            start = search_pos
        end = start + len(chunk)
        search_pos = end

        result.append((chunk, start, end))

    return result
