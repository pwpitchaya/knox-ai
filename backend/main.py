from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from dotenv import load_dotenv
from supabase import create_client
from pypdf import PdfReader
from docx import Document
from sentence_transformers import SentenceTransformer
import os
import uuid
import tempfile
from provenance import extract_sections, chunk_sections

# =========================
# Load Environment
# =========================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL not found in .env")

if not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_KEY not found in .env")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY
)

print("Loading embedding model...")

embedding_model = SentenceTransformer(
    "intfloat/multilingual-e5-base"
)

print("Embedding model ready.")
# =========================
# FastAPI App
# =========================

app = FastAPI(
    title="KNOX AI Backend",
    version="0.3.0"
)

# =========================
# Models
# ========================

class OrganizationCreate(BaseModel):
    name: str


class ContainerCreate(BaseModel):
    organization_id: str
    name: str
    description: str | None = None

class SearchQuery(BaseModel):
    query: str
    match_count: int = 5

class AskQuery(BaseModel):
    container_id: str
    query: str
    match_count: int = 3


# =========================
# Helper Functions
# =========================

def extract_text_from_pdf(file_path: str) -> str:
    text = ""

    reader = PdfReader(file_path)

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text.strip()


def extract_text_from_docx(file_path: str) -> str:
    document = Document(file_path)

    paragraphs = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            paragraphs.append(paragraph.text.strip())

    return "\n".join(paragraphs).strip()


def extract_text_from_txt(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read().strip()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="tis-620") as file:
            return file.read().strip()


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    chunks = []

    if not text:
        return chunks

    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start = end - overlap

        if start < 0:
            start = 0

    return chunks


def create_embedding(text: str):
    embedding = embedding_model.encode(text)
    return embedding.tolist()

def extract_text_by_file_type(file_path: str, file_type: str) -> str:
    file_type = file_type.lower()

    if file_type == "pdf":
        return extract_text_from_pdf(file_path)

    if file_type == "docx":
        return extract_text_from_docx(file_path)

    if file_type == "txt":
        return extract_text_from_txt(file_path)

    raise ValueError("Unsupported file type. Please upload PDF, DOCX, or TXT.")


# =========================
# Root
# =========================

@app.get("/")
def root():
    return {
        "status": "running",
        "project": "KNOX AI",
        "version": "0.3.0"
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "database": "connected"
    }


# =========================
# Organizations
# =========================

@app.post("/organizations")
def create_organization(data: OrganizationCreate):
    try:
        result = (
            supabase
            .table("organizations")
            .insert({
                "name": data.name
            })
            .execute()
        )

        return result.data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/organizations")
def list_organizations():
    try:
        result = (
            supabase
            .table("organizations")
            .select("*")
            .execute()
        )

        return result.data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================
# Containers
# =========================

@app.post("/containers")
def create_container(data: ContainerCreate):
    try:
        result = (
            supabase
            .table("containers")
            .insert({
                "organization_id": data.organization_id,
                "name": data.name,
                "description": data.description
            })
            .execute()
        )

        return result.data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/containers")
def list_containers():
    try:
        result = (
            supabase
            .table("containers")
            .select("*")
            .execute()
        )

        return result.data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================
# Documents
# =========================

@app.get("/documents")
def list_documents():
    try:
        result = (
            supabase
            .table("documents")
            .select("*")
            .execute()
        )

        return result.data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================
# Upload + Process Document
# =========================

@app.post("/upload")
async def upload_document(
    container_id: str,
    file: UploadFile = File(...)
):
    temp_file_path = None

    try:
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Missing file name"
            )

        extension = file.filename.split(".")[-1].lower()

        if extension not in ["pdf", "docx", "txt"]:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Please upload PDF, DOCX, or TXT."
            )

        unique_filename = f"{uuid.uuid4()}.{extension}"

        file_content = await file.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        storage_result = supabase.storage.from_("documents").upload(
            unique_filename,
            file_content,
            {
                "content-type": file.content_type
            }
        )

        document_result = (
            supabase
            .table("documents")
            .insert({
                "container_id": container_id,
                "file_name": file.filename,
                "file_type": extension,
                "file_url": unique_filename,
                "status": "processing"
            })
            .execute()
        )

        if not document_result.data:
            raise RuntimeError("Failed to create document record")

        document_id = document_result.data[0]["id"]

        sections = extract_sections(temp_file_path, extension)
        extracted_text = "\n".join(section["text"] for section in sections).strip()

        if not extracted_text:
            (
                supabase
                .table("documents")
                .update({
                    "status": "failed"
                })
                .eq("id", document_id)
                .execute()
            )

            raise HTTPException(
                status_code=400,
                detail="Could not extract text from document"
            )

        chunks = chunk_sections(sections, chunk_size=800, overlap=120)

        chunk_records = []

        for index, chunk in enumerate(chunks):
            embedding = create_embedding(chunk["text"])

            chunk_records.append({
                "document_id": document_id,
                "container_id": container_id,
                "chunk_text": chunk["text"],
                "page_number": chunk["page_number"],
                "embedding": embedding,
                "metadata": {
                    "chunk_index": index,
                    "page_number": chunk["page_number"],
                    "source_file": file.filename,
                    "stored_file": unique_filename,
                    "file_type": extension
             }
        })

        if chunk_records:
            (
                supabase
                .table("document_chunks")
                .insert(chunk_records)
                .execute()
            )

        (
            supabase
            .table("documents")
            .update({
                "status": "processed"
            })
            .eq("id", document_id)
            .execute()
        )

        return {
            "message": "Upload and processing successful",
            "document_id": document_id,
            "file_name": file.filename,
            "stored_file": unique_filename,
            "file_type": extension,
            "chunks_created": len(chunks),
            "status": "processed"
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.post("/search")
def semantic_search(data: SearchQuery):
    try:
        query_embedding = create_embedding(data.query)

        result = (
            supabase
            .rpc(
                "match_document_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_count": data.match_count
                }
            )
            .execute()
        )

        return {
            "query": data.query,
            "results": result.data
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post("/ask")
def ask_knox(data: AskQuery):
    try:
        query_embedding = create_embedding(data.query)

        search_result = (
            supabase
            .rpc(
                "match_chunks_by_container",
                {
                    "query_embedding": query_embedding,
                    "target_container_id": data.container_id,
                    "match_count": data.match_count
                }
            )
            .execute()
        )

        chunks = search_result.data or []

        if not chunks:
            return {
                "query": data.query,
                "answer": "ไม่พบข้อมูลนี้ในคลังความรู้ขององค์กร",
                "sources": []
            }

        best_chunk = chunks[0]
        context = best_chunk["chunk_text"]
        metadata = best_chunk.get("metadata") or {}
        source_file = metadata.get("source_file", "unknown")

        similarity = best_chunk.get("similarity", 0)

        if similarity < 0.65:
            return {
                "query": data.query,
                "answer": "ไม่พบข้อมูลที่เกี่ยวข้องมากพอในคลังความรู้นี้",
                "sources": [
                    {
                        "source_file": source_file,
                        "similarity": similarity,
                        "chunk_id": best_chunk["id"],
                        "page_number": best_chunk.get("page_number", metadata.get("page_number")),
                        "excerpt": context
                    }
                ]
            }

        return {
            "query": data.query,
            "answer": context,
            "sources": [
                {
                    "source_file": source_file,
                    "similarity": similarity,
                    "chunk_id": best_chunk["id"],
                        "page_number": best_chunk.get("page_number", metadata.get("page_number")),
                        "excerpt": context
                }
            ],
            "matched_chunks": chunks
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
