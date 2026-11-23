import os
import pymupdf as fitz
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(timeout=25000),
)

# Κατευθείαν τα πιο γρήγορα ενεργά μοντέλα χωρίς περιττές κλήσεις discovery
ACTIVE_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
]


class QuizQuestion(BaseModel):
    question: str = Field(description="Σύντομη ερώτηση κατανόησης")
    options: list[str] = Field(description="4 σύντομες επιλογές απάντησης")
    correct_index: int = Field(description="Δείκτης 0-3 της σωστής απάντησης")
    explanation: str = Field(description="Επεξήγηση σε 1 σύντομη πρόταση")


class StudyGuideResponse(BaseModel):
    title: str = Field(description="Σύντομος τίτλος (3-6 λέξεις)")
    simple_explanation: str = Field(description="Απλή εξήγηση σε 2 σύντομες παραγράφους στα Ελληνικά")
    key_takeaways: list[str] = Field(description="3 έως 4 σύντομα σημεία-κλειδιά (1 πρόταση το καθένα)")
    quiz: list[QuizQuestion] = Field(description="5 σύντομες ερωτήσεις πολλαπλής επιλογής")
    extracted_text: str = Field(default="", description="Το κείμενο των σημειώσεων")


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """Διαβάζει κείμενο από PDF ή αρχείο κειμένου απευθείας από τη μνήμη (RAM)."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_text = [page.get_text() for page in doc]
        return "\n\n".join(pages_text).strip()
    return file_bytes.decode("utf-8", errors="ignore").strip()


def _fast_generate_config(model_name: str, system_instruction: str, schema, temperature: float):
    kwargs = {
        "system_instruction": system_instruction,
        "response_mime_type": "application/json",
        "response_schema": schema,
        "temperature": temperature,
        "max_output_tokens": 1400,
    }
    if "lite" not in model_name.lower():
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    return types.GenerateContentConfig(**kwargs)


def generate_study_guide_and_quiz(notes_text: str) -> StudyGuideResponse:
    """Αναλύει τις σημειώσεις και παράγει Quiz με ελάχιστο latency."""
    trimmed_notes = notes_text[:6000]

    system_instruction = """
    Είσαι AI Study Assistant. Απάντησε στα Ελληνικά, σύντομα, καθαρά και περιεκτικά:
    1. Απλή εξήγηση του νοήματος σε 2 σύντομες παραγράφους.
    2. 3-4 σύντομα σημεία-κλειδιά (1 πρόταση το καθένα).
    3. 5 σύντομες ερωτήσεις κατανόησης (4 σύντομες επιλογές, 1 πρόταση επεξήγηση).
    """

    last_error = None
    for model_name in ACTIVE_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=f"ΣΗΜΕΙΩΣΕΙΣ:\n{trimmed_notes}",
                config=_fast_generate_config(model_name, system_instruction, StudyGuideResponse, 0.2),
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
    quiz: list[QuizQuestion] = Field(description="5 νέες σύντομες ερωτήσεις")


def generate_new_quiz(notes_text: str, previous_questions: list[str] = None) -> NewQuizResponse:
    """Παράγει γρήγορα ένα νέο σετ 5 ερωτήσεων."""
    trimmed_notes = notes_text[:6000]
    avoid_block = ""
    if previous_questions:
        joined = "\n".join(f"- {q}" for q in previous_questions)
        avoid_block = f"\nΜΗΝ επαναλάβεις:\n{joined}\n"

    system_instruction = """
    Δημιούργησε 5 ΝΕΕΣ, σύντομες ερωτήσεις πολλαπλής επιλογής (4 σύντομες επιλογές, 1 πρόταση επεξήγηση) στα Ελληνικά.
    """

    last_error = None
    for model_name in ACTIVE_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=f"ΣΗΜΕΙΩΣΕΙΣ:\n{trimmed_notes}\n{avoid_block}",
                config=_fast_generate_config(model_name, system_instruction, NewQuizResponse, 0.4),
            )
            return NewQuizResponse.model_validate_json(response.text)
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"Αποτυχία δημιουργίας νέου quiz: {last_error}")