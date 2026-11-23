import os
import time
import chromadb
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(timeout=12000),
)
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="msc_notes")

# Το σταθερό gemini-2.5-flash μπαίνει πρώτο για άμεση απόκριση χωρίς καθυστερήσεις
ACTIVE_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.1-flash-lite",
]


class Citation(BaseModel):
    source_file: str = Field(description="Το όνομα του αρχείου (π.χ. lecture1.pdf)")
    page_number: int = Field(description="Ο αριθμός σελίδας από όπου αντλήθηκε η πληροφορία")
    snippet: str = Field(description="Σύντομο χαρακτηριστικό απόσπασμα 1 πρότασης από το κείμενο")


class RAGResponse(BaseModel):
    answer: str = Field(description="Η αναλυτική απάντηση στην ερώτηση του χρήστη στα Ελληνικά (ή στη γλώσσα της ερώτησης)")
    found_in_notes: bool = Field(description="True αν η απάντηση προκύπτει από τα παρεχόμενα αποσπάσματα, False αν δεν υπάρχει πληροφορία")
    citations: list[Citation] = Field(description="Λίστα με τις ακριβείς πηγές που χρησιμοποιήθηκαν")


def generate_with_retry(prompt: str, system_instruction: str, response_schema):
    """Καλεί τα ενεργά μοντέλα με σύντομο backoff ώστε να μην ξεπερνά το όριο των 30s του Render."""
    last_error = None
    for attempt in range(1, 3):  # Έως 2 γύροι προσπαθειών
        for model_name in ACTIVE_MODELS:
            print(f"🤖 Προσπάθεια {attempt}/2 με {model_name}...", flush=True)
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        response_schema=response_schema,
                        temperature=0.1,
                    ),
                )
                return response.text
            except Exception as e:
                last_error = e
                err_str = str(e)
                print(f"⚠️ {model_name}: {type(e).__name__} - {err_str}", flush=True)
                if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                    wait_sec = attempt * 1.5
                    print(f"⏳ Αναμονή {wait_sec}s λόγω φόρτου server...", flush=True)
                    time.sleep(wait_sec)
                continue

    raise RuntimeError(f"Τα μοντέλα είναι προσωρινά υπερφορτωμένα. Τελευταίο σφάλμα: {last_error}")


def retrieve_context(query: str, top_k: int = 5) -> list[dict]:
    """Μετατρέπει την ερώτηση σε embedding και βρίσκει τα top_k πιο σχετικά chunks στη ChromaDB."""
    query_embedding = client.models.embed_content(
        model="gemini-embedding-001",
        contents=query,
    ).embeddings[0].values

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    retrieved_chunks = []
    if results["documents"] and results["documents"][0]:
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            retrieved_chunks.append({
                "text": doc,
                "source": meta["source"],
                "page": meta["page"],
                "distance": round(dist, 4)
            })
    return retrieved_chunks


def ask_notes(query: str, top_k: int = 5) -> RAGResponse:
    """Εκτελεί το πλήρες RAG pipeline: Retrieval -> Augmented Prompt -> Structured Generation."""
    print("🔎 1/3 Αναζήτηση στις σημειώσεις (ChromaDB)...", flush=True)
    chunks = retrieve_context(query, top_k=top_k)

    if not chunks:
        return RAGResponse(
            answer="Η βάση γνώσης είναι άδεια. Τρέξε πρώτα το ingest.py με τα αρχεία σου.",
            found_in_notes=False,
            citations=[]
        )

    print(f"📄 2/3 Βρέθηκαν {len(chunks)} αποσπάσματα. Σύνταξη απάντησης...", flush=True)

    context_blocks = []
    for i, c in enumerate(chunks, start=1):
        context_blocks.append(
            f"[Πηγή {i} | Αρχείο: {c['source']} | Σελίδα: {c['page']}]\n{c['text']}"
        )
    formatted_context = "\n\n---\n\n".join(context_blocks)

    system_instruction = """
    Είσαι ένας αυστηρός και ακριβής ακαδημαϊκός βοηθός για μεταπτυχιακό στην Τεχνητή Νοημοσύνη.
    Κανόνες:
1. Απάντησε στην ερώτηση του χρήστη ΑΠΟΚΛΕΙΣΤΙΚΑ με βάση τις Πηγές που σου δίνονται παρακάτω.
2. ΜΗΝ χρησιμοποιείς εξωτερικές γνώσεις και ΜΗΝ υποθέτεις πράγματα που δεν γράφονται ρητά στις πηγές.
3. Αν οι πηγές δεν περιέχουν την απάντηση, θέσε found_in_notes=False και εξήγησε ευγενικά ότι η πληροφορία δεν βρέθηκε στις σημειώσεις.
4. Συμπλήρωσε με ακρίβεια τα citations (όνομα αρχείου και αριθμό σελίδας) για κάθε πηγή που στήριξε την απάντησή σου.
    """

    prompt = f"""
    ΠΗΓΕΣ ΑΠΟ ΣΗΜΕΙΩΣΕΙΣ:
    {formatted_context}

    ΕΡΩΤΗΣΗ ΧΡΗΣΤΗ:
    {query}
    """

    raw_json = generate_with_retry(prompt, system_instruction, RAGResponse)
    return RAGResponse.model_validate_json(raw_json)


if __name__ == "__main__":
    test_question = input("Κάνε μια ερώτηση πάνω στις σημειώσεις σου: ")
    result = ask_notes(test_question)

    print("\n" + "=" * 50)
    print(f"📌 Απάντηση (Βρέθηκε στις σημειώσεις: {result.found_in_notes}):\n")
    print(result.answer)
    print("\n📚 Πηγές (Citations):")
    for cit in result.citations:
        print(f"  - {cit.source_file} (Σελ. {cit.page_number}): \"{cit.snippet}\"")
    print("=" * 50)