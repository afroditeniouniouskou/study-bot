import os
import time
from pathlib import Path
import pymupdf
import chromadb
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="msc_notes")


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if len(chunk) > 50:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Παράγει embeddings για μια ομάδα κειμένων ταυτόχρονα."""
    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=texts,
    )
    return [emb.values for emb in response.embeddings]


def extract_documents(data_dir: str = "./data") -> list[dict]:
    docs = []
    for file_path in Path(data_dir).rglob("*"):
        if file_path.suffix.lower() == ".pdf":
            pdf = pymupdf.open(file_path)
            for page_num, page in enumerate(pdf, start=1):
                text = page.get_text("text")
                for idx, chunk in enumerate(chunk_text(text)):
                    docs.append({
                        "id": f"{file_path.name}_p{page_num}_c{idx}",
                        "text": chunk,
                        "metadata": {
                            "source": file_path.name,
                            "page": page_num,
                            "type": "pdf"
                        }
                    })
        elif file_path.suffix.lower() == ".py":
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            for idx, chunk in enumerate(chunk_text(text, chunk_size=1200, overlap=150)):
                docs.append({
                    "id": f"{file_path.name}_c{idx}",
                    "text": f"Python file ({file_path.name}):\n{chunk}",
                    "metadata": {
                        "source": file_path.name,
                        "page": 1,
                        "type": "python"
                    }
                })
    return docs


def run_ingestion(batch_size: int = 40):
    print("🔍 Διαβάζω τα αρχεία από τον φάκελο ./data ...")
    documents = extract_documents("./data")
    
    if not documents:
        print("⚠️ Δεν βρέθηκαν PDF ή .py αρχεία στον φάκελο ./data!")
        return

    # Ελέγχουμε ποια chunks υπάρχουν ήδη στη βάση για να μην τα ξαναχρεωθούμε
    existing_ids = set(collection.get()["ids"])
    pending_docs = [d for d in documents if d["id"] not in existing_ids]

    print(f"📄 Σύνολο: {len(documents)} chunks | Ήδη αποθηκευμένα: {len(existing_ids)} | Απομένουν: {len(pending_docs)}")
    
    if not pending_docs:
        print("✅ Όλα τα αρχεία είναι ήδη στη βάση γνώσης!")
        return

    requests_this_minute = 0

    for i in range(0, len(pending_docs), batch_size):
        batch = pending_docs[i:i + batch_size]

        # Αν φτάνουμε κοντά στο όριο των 100 requests/λεπτό του Free Tier, περιμένουμε 62 δευτ.
        if requests_this_minute + len(batch) > 90:
            print("⏳ Αναμονή 62 δευτερολέπτων για ανανέωση του API rate limit...")
            time.sleep(62)
            requests_this_minute = 0

        texts = [d["text"] for d in batch]
        embeddings = get_embeddings_batch(texts)

        collection.upsert(
            ids=[d["id"] for d in batch],
            embeddings=embeddings,
            documents=texts,
            metadatas=[d["metadata"] for d in batch]
        )
        requests_this_minute += len(batch)
        print(f"   Προχώρησε: {min(i + batch_size, len(pending_docs))}/{len(pending_docs)} νέα chunks")

    print("✅ Ολοκληρώθηκε! Η βάση γνώσης είναι έτοιμη στον φάκελο ./chroma_db")


if __name__ == "__main__":
    run_ingestion()