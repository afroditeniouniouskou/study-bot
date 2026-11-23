import os
import time
import pymupdf as fitz
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(timeout=30000),
)


def get_available_flash_models() -> list[str]:
    """Εντοπίζει δυναμικά τα ενεργά γρήγορα μοντέλα (flash) του API key."""
    discovered = []
    try:
        for m in client.models.list():
            name = (m.name or "").replace("models/", "")
            actions = getattr(m, "supported_actions", None) or []
            if "generateContent" in actions and "flash" in name.lower():
                if not any(x in name.lower() for x in ["image", "audio", "tts", "live", "embedding"]):
                    discovered.append(name)
    except Exception as e:
        print(f"⚠️ Σφάλμα κατά το list models: {e}", flush=True)

    # Προτεραιότητα στα flash-lite (ταχύτερα) και έπειτα στα flash
    discovered.sort(key=lambda x: (0 if "lite" in x else 1, x), reverse=False)
    return discovered or ["gemini-3.1-flash-lite", "gemini-3.8-flash"]


ACTIVE_MODELS = get_available_flash_models()
print(f"✅ Ενεργά μοντέλα (με σειρά ταχύτητας): {ACTIVE_MODELS}", flush=True)


class QuizQuestion(BaseModel):
    question: str = Field(description="Η ερώτηση κατανόησης πάνω στις σημειώσεις")
    options: list[str] = Field(description="Ακριβώς 4 πιθανές απαντήσεις πολλαπλής επιλογής")
    correct_index: int = Field(description="Ο δείκτης (0, 1, 2 ή 3) της σωστής απάντησης στη λίστα options")
    explanation: str = Field(description="Σύντομη επεξήγηση (1 πρόταση) γιατί αυτή είναι η σωστή απάντηση")


class StudyGuideResponse(BaseModel):
    title: str = Field(description="Σύντομος τίτλος ενότητας")
    simple_explanation: str = Field(description="Καθαρή, απλή ανάλυση των σημειώσεων στα Ελληνικά σε 2-3 παραγράφους")
    key_takeaways: list[str] = Field(description="3 έως 5 σύντομα σημεία-κλειδιά")
    quiz: list[QuizQuestion] = Field(description="5 ερωτήσεις πολλαπλής επιλογής με 4 επιλογές")
    extracted_text: str = Field(default="", description="Το κείμενο που εξήχθη για μελλοντικά quizzes")


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """Διαβάζει κείμενο από PDF ή αρχείο κειμένου/κώδικα απευθείας από τη μνήμη (RAM)."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_text = [page.get_text() for page in doc]
        return "\n\n".join(pages_text).strip()
    return file_bytes.decode("utf-8", errors="ignore").strip()


def _fast_generate_config(system_instruction: str, schema, temperature: float):
    """Ρύθμιση για μέγιστη ταχύτητα απόκρισης χωρίς χρονοβόρο thinking."""
    try:
        return types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
    except Exception:
        return types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
        )


def generate_study_guide_and_quiz(notes_text: str) -> StudyGuideResponse:
    """Αναλύει τις σημειώσεις με απλά λόγια και παράγει διαδραστικό Quiz σε μία κλήση."""
    trimmed_notes = notes_text[:10000]

    system_instruction = """
    Είσαι μεταδοτικός καθηγητής και AI Study Assistant.
    Πάρε τις σημειώσεις και δώσε:
    1. Απλή, περιεκτική εξήγηση (2-3 σύντομες παράγραφοι) στα Ελληνικά.
    2. 3 έως 5 σύντομα key takeaways.
    3. 5 στοχευμένες ερωτήσεις πολλαπλής επιλογής (4 επιλογές η καθεμία) με σύντομη επεξήγηση.
    Να είσαι άμεσος, σαφής και περιεκτικός.
    """

    last_error = None
    for model_name in ACTIVE_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=f"ΣΗΜΕΙΩΣΕΙΣ:\n{trimmed_notes}",
                config=_fast_generate_config(system_instruction, StudyGuideResponse, 0.2),
            )
            result = StudyGuideResponse.model_validate_json(response.text)
            result.extracted_text = trimmed_notes
            return result
        except Exception as e:
            last_error = e
            print(f"⚠️ {model_name}: {type(e).__name__} - {e}", flush=True)
            continue

    raise RuntimeError(f"Το μοντέλο είναι προσωρινά απασχολημένο. Δοκίμασε ξανά. ({last_error})")


class NewQuizResponse(BaseModel):
    quiz: list[QuizQuestion] = Field(description="5 νέες ερωτήσεις πολλαπλής επιλογής")


def generate_new_quiz(notes_text: str, previous_questions: list[str] = None) -> NewQuizResponse:
    """Παράγει ένα νέο σετ 5 ερωτήσεων αποφεύγοντας τις προηγούμενες."""
    trimmed_notes = notes_text[:10000]
    avoid_block = ""
    if previous_questions:
        joined = "\n".join(f"- {q}" for q in previous_questions)
        avoid_block = f"\nΜΗΝ επαναλάβεις αυτές τις ερωτήσεις:\n{joined}\n"

    system_instruction = """
    Δημιούργησε 5 ΝΕΕΣ, σύντομες ερωτήσεις πολλαπλής επιλογής (4 επιλογές η καθεμία)
    πάνω σε διαφορετικά σημεία των σημειώσεων. Απάντησε στα Ελληνικά.
    """

    last_error = None
    for model_name in ACTIVE_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=f"ΣΗΜΕΙΩΣΕΙΣ:\n{trimmed_notes}\n{avoid_block}",
                config=_fast_generate_config(system_instruction, NewQuizResponse, 0.4),
            )
            return NewQuizResponse.model_validate_json(response.text)
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"Αποτυχία δημιουργίας νέου quiz: {last_error}")