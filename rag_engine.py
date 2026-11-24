import os
import time
import random
import pymupdf as fitz
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(timeout=40000),
)

ACTIVE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
]


class StudySection(BaseModel):
    heading: str = Field(description="Τίτλος της υποενότητας / σελίδας")
    explanation: str = Field(
        description="Αναλυτική, κατανοητή επεξήγηση του 'γιατί' και 'πώς' λειτουργεί η έννοια (2 γεμάτες παράγραφοι)"
    )
    example: str = Field(description="Ένα συγκεκριμένο, ρεαλιστικό παράδειγμα εφαρμογής ή αναλογία")


class QuizQuestion(BaseModel):
    question: str = Field(description="Ερώτηση κατανόησης πάνω στις σημειώσεις")
    options: list[str] = Field(description="4 επιλογές απάντησης")
    correct_index: int = Field(description="Δείκτης 0-3 της σωστής απάντησης")
    explanation: str = Field(description="Σύντομη επεξήγηση γιατί αυτή είναι η σωστή απάντηση")


class StudyGuideResponse(BaseModel):
    title: str = Field(description="Γενικός τίτλος του κεφαλαίου")
    sections: list[StudySection] = Field(
        description="3 έως 4 αναλυτικές σελίδες/ενότητες θεωρίας με επεξηγήσεις και παραδείγματα"
    )
    key_takeaways: list[str] = Field(description="3 έως 5 βασικά συμπεράσματα-κλειδιά")
    quiz: list[QuizQuestion] = Field(description="5 ερωτήσεις πολλαπλής επιλογής")
    extracted_text: str = Field(default="", description="Το κείμενο των σημειώσεων")


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """Διαβάζει κείμενο από PDF ή αρχείο κειμένου απευθείας από τη μνήμη (RAM)."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        pages_text = []
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc[:15]:
                pages_text.append(page.get_text())
                if sum(len(p) for p in pages_text) > 12000:
                    break
        return "\n\n".join(pages_text).strip()
    return file_bytes[:50000].decode("utf-8", errors="ignore").strip()


def _fast_generate_config(model_name: str, system_instruction: str, schema, temperature: float):
    kwargs = {
        "system_instruction": system_instruction,
        "response_mime_type": "application/json",
        "response_schema": schema,
        "temperature": temperature,
        "max_output_tokens": 2400,
    }
    if "flash" in model_name.lower() and "lite" not in model_name.lower():
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    return types.GenerateContentConfig(**kwargs)


def _call_with_resilient_retry(contents: str, system_instruction: str, schema, temperature: float) -> str:
    """Γρήγορη εναλλαγή Flash μοντέλων με σύντομο backoff σε 503/429."""
    last_error = None
    max_rounds = 3

    for round_idx in range(1, max_rounds + 1):
        for model_name in ACTIVE_MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=_fast_generate_config(model_name, system_instruction, schema, temperature),
                )
                if response and response.text:
                    return response.text
            except Exception as e:
                last_error = e
                err_str = str(e)
                print(
                    f"⚠️ [Γύρος {round_idx}/{max_rounds}] {model_name}: {type(e).__name__} -> {err_str}",
                    flush=True,
                )

                if "404" in err_str or "NOT_FOUND" in err_str or "400" in err_str or "INVALID_ARGUMENT" in err_str:
                    continue

                if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    time.sleep(0.6 * round_idx + random.uniform(0.1, 0.3))
                    continue

        if round_idx < max_rounds:
            time.sleep(1.0 * round_idx)

    raise RuntimeError(
        f"Σφάλμα επικοινωνίας με Gemini API: {last_error}"
    ) from last_error


def generate_study_guide_and_quiz(notes_text: str) -> StudyGuideResponse:
    """Παράγει αναλυτικό οδηγό με σελίδες/παραδείγματα και διαδραστικό Quiz."""
    trimmed_notes = notes_text[:9000]

    system_instruction = """
    Είσαι ένας εξαιρετικός, μεταδοτικός καθηγητής. Απάντησε στα Ελληνικά:
1. Χώρισε την ύλη σε 3 έως 4 λογικές ενότητες/σελίδες (sections). Για κάθε ενότητα δώσε:
  - Αναλυτική, σε βάθος επεξήγηση με απλά λόγια (2 γεμάτες παράγραφοι), εξηγώντας το 'γιατί' και το 'πώς'.
  - Ένα συγκεκριμένο, κατανοητό πρακτικό παράδειγμα.
2. Δώσε 3-5 βασικά σημεία-κλειδιά (key_takeaways).
3. Δημιούργησε 5 ουσιαστικές ερωτήσεις πολλαπλής επιλογής (4 επιλογές η καθεμία) με επεξήγηση.
    """

    raw_json = _call_with_resilient_retry(
        contents=f"ΣΗΜΕΙΩΣΕΙΣ:\n{trimmed_notes}",
        system_instruction=system_instruction,
        schema=StudyGuideResponse,
        temperature=0.25,
    )
    result = StudyGuideResponse.model_validate_json(raw_json)
    result.extracted_text = trimmed_notes
    return result


class NewQuizResponse(BaseModel):
    quiz: list[QuizQuestion] = Field(description="5 νέες ερωτήσεις πολλαπλής επιλογής")


def generate_new_quiz(notes_text: str, previous_questions: list[str] = None) -> NewQuizResponse:
    """Παράγει ένα νέο σετ 5 ερωτήσεων."""
    trimmed_notes = notes_text[:9000]
    avoid_block = ""
    if previous_questions:
        joined = "\n".join(f"- {q}" for q in previous_questions)
        avoid_block = f"\nΜΗΝ επαναλάβεις:\n{joined}\n"

    system_instruction = """
    Δημιούργησε 5 ΝΕΕΣ ερωτήσεις πολλαπλής επιλογής (4 επιλογές η καθεμία, με επεξήγηση) στα Ελληνικά.
    """

    raw_json = _call_with_resilient_retry(
        contents=f"ΣΗΜΕΙΩΣΕΙΣ:\n{trimmed_notes}\n{avoid_block}",
        system_instruction=system_instruction,
        schema=NewQuizResponse,
        temperature=0.4,
    )
    return NewQuizResponse.model_validate_json(raw_json)