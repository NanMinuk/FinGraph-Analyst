from typing import List, Dict, Any
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_documents_to_chunks(
    documents: List[Dict[str, Any]],
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> List[Dict[str, Any]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunked_docs: List[Dict[str, Any]] = []

    for doc in documents:
        text = (doc.get("text") or "").strip()
        if not text:
            continue

        base_doc = Document(
            page_content=text,
            metadata={
                "doc_id": doc.get("doc_id"),
                "title": doc.get("title"),
                "source": doc.get("source"),
                "date": doc.get("date"),
                "company": doc.get("company"),
                "url": doc.get("url"),
            },
        )

        chunks = splitter.create_documents(
            texts=[base_doc.page_content],
            metadatas=[base_doc.metadata],
        )

        for idx, chunk in enumerate(chunks):
            chunked_docs.append({
                "doc_id": chunk.metadata.get("doc_id"),
                "chunk_id": f"{chunk.metadata.get('doc_id', 'unknown')}_chunk_{idx}",
                "title": chunk.metadata.get("title"),
                "source": chunk.metadata.get("source"),
                "date": chunk.metadata.get("date"),
                "company": chunk.metadata.get("company"),
                "url": chunk.metadata.get("url"),
                "text": chunk.page_content,
            })

    return chunked_docs