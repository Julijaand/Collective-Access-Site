"""
Ingest knowledge base documents into ChromaDB vector database.
Run this once (and re-run whenever docs are updated):

    cd saas-backend
    python -m ai.ingest

What it does:
  - Reads markdown files from ai/docs/
  - Splits them into overlapping chunks
  - Embeds with sentence-transformers/all-MiniLM-L6-v2
  - Stores in ChromaDB at ai/vector_db/
"""

from pathlib import Path
import re
import shutil

DOCS_DIR = Path(__file__).parent / "docs"
VECTOR_DB_PATH = Path(__file__).parent / "vector_db"
COLLECTION_NAME = "ca_knowledge"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 600   # characters per chunk
CHUNK_OVERLAP = 80


def split_markdown(text: str, title: str) -> list[dict]:
    """
    Split a markdown document into chunks, preserving section headings as metadata.
    Returns list of {content, title, section}.
    """
    chunks = []
    current_section = "Introduction"
    current_lines: list[str] = []

    for line in text.splitlines():
        # Detect headings (## or ###)
        heading_match = re.match(r'^#{1,3}\s+(.+)', line)
        if heading_match:
            # Flush current chunk
            block = "\n".join(current_lines).strip()
            if block:
                chunks.append({
                    "content": block,
                    "title": title,
                    "section": current_section,
                })
                current_lines = []
            current_section = heading_match.group(1).strip()
        else:
            current_lines.append(line)

    # Flush final chunk
    block = "\n".join(current_lines).strip()
    if block:
        chunks.append({
            "content": block,
            "title": title,
            "section": current_section,
        })

    # Further split large chunks
    result = []
    for chunk in chunks:
        text_block = chunk["content"]
        if len(text_block) <= CHUNK_SIZE:
            result.append(chunk)
        else:
            # Slide window
            start = 0
            while start < len(text_block):
                end = start + CHUNK_SIZE
                result.append({
                    "content": text_block[start:end],
                    "title": chunk["title"],
                    "section": chunk["section"],
                })
                start += CHUNK_SIZE - CHUNK_OVERLAP

    return result


def main():
    print("=" * 60)
    print("INGESTING KNOWLEDGE BASE INTO CHROMADB")
    print("=" * 60)

    # --- Load docs ---
    doc_files = sorted(DOCS_DIR.glob("*.md"))
    if not doc_files:
        print(f"❌ No .md files found in {DOCS_DIR}")
        return

    print(f"\nFound {len(doc_files)} documents:")
    for f in doc_files:
        print(f"  - {f.name}")

    # --- Build chunks ---
    all_chunks = []
    for doc_file in doc_files:
        title = doc_file.stem.replace("_", " ").title()
        text = doc_file.read_text(encoding="utf-8")
        chunks = split_markdown(text, title)
        all_chunks.extend(chunks)
        print(f"  ✓ {doc_file.name} → {len(chunks)} chunks")

    print(f"\nTotal chunks to embed: {len(all_chunks)}")

    # --- Load embedding model ---
    print(f"\nLoading embedding model ({EMBED_MODEL})...")
    from langchain_huggingface import HuggingFaceEmbeddings
    embedding = HuggingFaceEmbeddings(model_name=EMBED_MODEL)

    # --- Rebuild vector DB (clear contents, but keep the mount-point dir) ---
    if VECTOR_DB_PATH.exists():
        print(f"\nClearing old vector DB contents at {VECTOR_DB_PATH}...")
        for item in VECTOR_DB_PATH.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    print(f"Creating new vector DB at {VECTOR_DB_PATH}...")

    from langchain_chroma import Chroma
    from langchain_core.documents import Document

    documents = [
        Document(
            page_content=chunk["content"],
            metadata={
                "title": chunk["title"],
                "section": chunk["section"],
            },
        )
        for chunk in all_chunks
    ]

    Chroma.from_documents(
        documents=documents,
        embedding=embedding,
        collection_name=COLLECTION_NAME,
        persist_directory=str(VECTOR_DB_PATH),
    )

    print("\n" + "=" * 60)
    print(f"✅ INGESTION COMPLETE — {len(documents)} chunks stored")
    print("=" * 60)
    print(f"\nVector DB ready at: {VECTOR_DB_PATH}")
    print("Start the backend and test with: POST /api/chat")


if __name__ == "__main__":
    main()
