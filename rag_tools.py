# rag_tools.py

from typing import List
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# Se quiser eliminar o warning no futuro:
# from langchain_huggingface import HuggingFaceEmbeddings

# Vectorstore global
_vectorstore = None

# Embeddings locais (sem quota, sem API externa)
_embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


def build_vectorstore_from_pdfs(pdf_paths: List[str]) -> None:
    """
    Lê os PDFs, divide em chunks e constrói o índice vetorial FAISS
    usando embeddings locais.
    """
    global _vectorstore

    if not pdf_paths:
        return

    docs = []
    for path in pdf_paths:
        loader = PyPDFLoader(path)
        docs.extend(loader.load())

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    chunks = splitter.split_documents(docs)

    _vectorstore = FAISS.from_documents(chunks, _embeddings)


def pdf_rag_search(query: str, k: int = 4) -> str:
    """
    Faz busca vetorial nos PDFs já indexados e devolve trechos relevantes.
    Essa função é o "nó de ferramenta" utilizado pelo LangGraph.
    """
    if _vectorstore is None:
        return "Nenhum PDF foi indexado ainda. Faça upload dos arquivos primeiro."

    docs = _vectorstore.similarity_search(query, k=k)
    partes = []
    for i, d in enumerate(docs, start=1):
        partes.append(f"[Trecho {i}]\n{d.page_content}\n")
    return "\n\n".join(partes)
