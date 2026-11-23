import os
import time
import pymupdf as fitz  # PyMuPDF για άμεση ανάγνωση PDF στη RAM
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(timeout=45000),
)

ACTIVE_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.1-pro-preview",
]


class QuizQuestion(BaseModel):
    question: str = Field(description="Η ερώτηση κατανόησης πάνω στις σημειώσεις")
    options: list[str] = Field(description="Ακριβώς 4 πιθανές απαντήσεις πολλαπλής επιλογής")
    correct_index: int = Field(description="Ο δείκτης (0, 1, 2 ή 3) της σωστής απάντησης στη λίστα options")
    explanation: str = Field(description="Σύντομη, ξεκάθαρη επεξήγηση γιατί αυτή είναι η σωστή απάντηση")


class StudyGuideResponse(BaseModel):
    title: str = Field(description="Ένας σύντομος, περιγραφικός τίτλος για την ενότητα")
    simple_explanation: str = Field(description="Απλή, επεξηγηματική και κατανοητή ανάλυση του νοήματος των σημειώσεων στα Ελληνικά, σαν να το εξηγεί ένας καλός καθηγητής")
    key_takeaways: list[str] = Field(description="3 έως 6 βασικά σημεία-κλειδιά που πρέπει οπωσδήποτε να θυμάται ο φοιτητής")
    quiz: list[QuizQuestion] = Field(description="5 ερωτήσεις πολλαπλής επιλογής για να ελέγξει ο χρήστης αν κατανόησε το κείμενο")


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """Διαβάζει κείμενο από PDF ή αρχείο κειμένου/κώδικα απευθείας από τη μνήμη (RAM)."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_text = [page.get_text() for page in doc]
        return "\n\n".join(pages_text).strip()
    return file_bytes.decode("utf-8", errors="ignore").strip()


def generate_study_guide_and_quiz(notes_text: str) -> StudyGuideResponse:
    """Αναλύει τις σημειώσεις με απλά λόγια και παράγει διαδραστικό Quiz σε μία κλήση."""
    trimmed_notes = notes_text[:18000]

    system_instruction = """
    Είσαι ένας εξαιρετικός, μεταδοτικός καθηγητής και AI Study Assistant.
    Στόχος σου είναι να πάρεις τις σημειώσεις του χρήστη και:
1. Να εξηγήσεις το νόημά τους με απλά, κατανοητά λόγια (χωρίς περιττή ακαδημαϊκή δυσκολία), αναλύοντας το 'γιατί' και το 'πώς' λειτουργούν οι έννοιες.
2. Να ξεχωρίσεις τα πιο σημαντικά σημεία-κλειδιά (key takeaways).
3. Να δημιουργήσεις 5 ουσιαστικές ερωτήσεις πολλαπλής επιλογής (quiz) που ελέγχουν την πραγματική κατανόηση (όχι απλή αποστήθιση) και έχουν 4 επιλογές η καθεμία.
    Απάντησε στη γλώσσα των σημειώσεων (κατά προτίμηση στα Ελληνικά).
    """

    prompt = f"""
    ΣΗΜΕΙΩΣΕΙΣ ΧΡΗΣΤΗ:
    {trimmed_notes}
    """

    last_error = None
    for attempt in range(1, 3):
        for model_name in ACTIVE_MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        response_schema=StudyGuideResponse,
                        temperature=0.2,
                    ),
                )
                return StudyGuideResponse.model_validate_json(response.text)
            except Exception as e:
                last_error = e
                err_str = str(e)
                print(f"⚠️ {model_name}: {type(e).__name__} - {err_str}", flush=True)
                if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                    time.sleep(attempt * 1.5)
                continue

    raise RuntimeError(f"Το μοντέλο είναι προσωρινά απασχολημένο. Δοκίμασε ξανά. ({last_error})")


class NewQuizResponse(BaseModel):
    quiz: list[QuizQuestion] = Field(description="5 νέες, διαφορετικές ερωτήσεις πολλαπλής επιλογής πάνω στις ίδιες σημειώσεις")


def generate_new_quiz(notes_text: str, previous_questions: list[str] = None) -> NewQuizResponse:
    """Παράγει ένα νέο σετ 5 ερωτήσεων αποφεύγοντας τις προηγούμενες."""
    trimmed_notes = notes_text[:18000]
    avoid_block = ""
    if previous_questions:
        joined = "\n".join(f"- {q}" for q in previous_questions)
        avoid_block = f"\nΑΠΕΦΥΓΕ να επαναλάβεις τις παρακάτω ερωτήσεις που έγιναν ήδη:\n{joined}\n"

    system_instruction = """
    Είσαι ένας AI Study Assistant. Δημιούργησε 5 ΝΕΕΣ ερωτήσεις πολλαπλής επιλογής (με 4 επιλογές η καθεμία)
    που ελέγχουν διαφορετικές πτυχές ή λεπτομέρειες των σημειώσεων του χρήστη.
    Απάντησε στη γλώσσα των σημειώσεων.
    """

    prompt = f"""
    ΣΗΜΕΙΩΣΕΙΣ ΧΡΗΣΤΗ:
    {trimmed_notes}
    {avoid_block}
    """

    last_error = None
    for attempt in range(1, 3):
        for model_name in ACTIVE_MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        response_schema=NewQuizResponse,
                        temperature=0.4,
                    ),
                )
                return NewQuizResponse.model_validate_json(response.text)
            except Exception as e:
                last_error = e
                time.sleep(attempt * 1.5)
                continue

    raise RuntimeError(f"Αποτυχία δημιουργίας νέου quiz: {last_error}")