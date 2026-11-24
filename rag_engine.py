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
    http_options=types.HttpOptions(timeout=40000, api_version="v1beta"),
)


def _discover_available_models() -> list[str]:
    """Βρίσκει αυτόματα τα ενεργά και σταθερά Gemini μοντέλα που υποστηρίζουν generateContent."""
    fallback = [
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
        "gemini-3-flash-preview",
        "gemini-3.1-flash-lite-preview",
        "gemini-3.1-pro-preview",
        "gemini-pro-latest",
    ]
    try:
        discovered = []
        for m in client.models.list():
            name = (m.name or "").replace("models/", "")
            actions = m.supported_actions or []
            if "gemini" in name.lower() and "generateContent" in actions:
                if not any(
                    x in name.lower()
                    for x in ["embedding", "imagen", "veo", "tts", "audio", "robotics", "computer"]
                ):
                    discovered.append(name)

        if discovered:
            stable = [m for m in discovered if not any(x in m.lower() for x in ["omni", "exp"])]
            pool = stable if stable else discovered

            priority = [
                "gemini-flash-latest",
                "gemini-flash-lite-latest",
                "gemini-3-flash-preview",
                "gemini-3.1-flash-lite-preview",
                "gemini-3.1-pro-preview",
                "gemini-pro-latest",
            ]
            ordered = [m for m in priority if m in pool]
            for m in sorted(pool, reverse=True):
                if m not in ordered:
                    ordered.append(m)

            print(f"✅ Διαθέσιμα Gemini μοντέλα: {ordered[:6]}", flush=True)
            return ordered[:6]
    except Exception as e:
        print(f"⚠️ Αδυναμία ανάκτησης λίστας μοντέλων ({e}), χρήση fallback.", flush=True)

    return fallback


ACTIVE_MODELS = _discover_available_models()


class StudySection(BaseModel):
    heading: str = Field(description="Απλός, ξεκάθαρος τίτλος της ενότητας")
    explanation: str = Field(
        description="Πολύ απλοϊκή, κατανοητή επεξήγηση σε φιλικό τόνο (2-3 παράγραφοι), σαν να τα εξηγείς προφορικά σε έναν φίλο χωρίς δύσκολη ορολογία"
    )
    example: str = Field(description="Ένα καθημερινό, ρεαλιστικό παράδειγμα ή αναλογία από την πραγματική ζωή")


class QuizQuestion(BaseModel):
    question: str = Field(description="Ερώτηση κατανόησης πάνω στις σημειώσεις")
    options: list[str] = Field(description="4 επιλογές απάντησης")
    correct_index: int = Field(description="Δείκτης 0-3 της σωστής απάντησης")
    explanation: str = Field(description="Απλή επεξήγηση γιατί αυτή είναι η σωστή απάντηση")


class StudyGuideResponse(BaseModel):
    title: str = Field(description="Γενικός τίτλος του κεφαλαίου")
    sections: list[StudySection] = Field(
        description="3 έως 4 αναλυτικές, πολύ κατανοητές ενότητες θεωρίας με επεξηγήσεις και παραδείγματα"
    )
    key_takeaways: list[str] = Field(description="3 έως 5 βασικά συμπεράσματα-κλειδιά με απλά λόγια")
    quiz: list[QuizQuestion] = Field(description="5 ερωτήσεις πολλαπλής επιλογής")
    extracted_text: str = Field(default="", description="Το κείμενο των σημειώσεων")


class VoiceAnswerResponse(BaseModel):
    answer: str = Field(
        description="Πολύ απλοϊκή, προφορική και φιλική απάντηση 3-5 προτάσεων στα Ελληνικά, χωρίς σύμβολα markdown, έτοιμη να διαβαστεί δυνατά"
    )


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


def _fast_generate_config(system_instruction: str, schema, temperature: float):
    return types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=schema,
        temperature=temperature,
        max_output_tokens=2800,
    )


def _call_with_resilient_retry(contents: str, system_instruction: str, schema, temperature: float) -> str:
    """Γρήγορη εναλλαγή διαθέσιμων μοντέλων με σύντομο backoff σε 503/429."""
    global ACTIVE_MODELS
    if not ACTIVE_MODELS:
        ACTIVE_MODELS = _discover_available_models()

    last_error = None
    max_rounds = 3

    for round_idx in range(1, max_rounds + 1):
        for model_name in ACTIVE_MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=_fast_generate_config(system_instruction, schema, temperature),
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
        f"Σφάλμα επικοινωνίας με Gemini API (μοντέλα: {ACTIVE_MODELS}): {last_error}"
    ) from last_error


def generate_study_guide_and_quiz(notes_text: str) -> StudyGuideResponse:
    """Παράγει εξαιρετικά απλοϊκό, επεξηγηματικό οδηγό και διαδραστικό Quiz."""
    trimmed_notes = notes_text[:9000]

    system_instruction = """
    Είσαι ο πιο μεταδοτικός, υπομονετικός καθηγητής. Ο στόχος σου είναι να κάνεις ακόμα και τις πιο δύσκολες έννοιες απολύτως ξεκάθαρες σε κάποιον που τις βλέπει πρώτη φορά.
    Απάντησε στα Ελληνικά:
    1. Χώρισε την ύλη σε 3 έως 4 λογικές ενότητες (sections). Για κάθε ενότητα:
       - Εξήγησέ την με ΠΟΛΥ ΑΠΛΑ, καθημερινά λόγια (2-3 γεμάτες παράγραφοι). Απόφυγε τη στείρα ακαδημαϊκή ορολογία — κι αν αναφέρεις έναν τεχνικό όρο, εξήγησέ τον αμέσως σε παρένθεση με απλά ελληνικά. Ξεκίνα από το "τι πρόβλημα λύνει αυτό;" και μετά εξήγησε βήμα-βήμα "πώς δουλεύει".
       - Δώσε ένα ζωντανό, καθημερινό παράδειγμα (π.χ. με μαγειρική, οδήγηση, ψώνια, παιχνίδι) ώστε να «κλειδώσει» η κατανόηση.
    2. Δώσε 3-5 βασικά συμπεράσματα-κλειδιά (key_takeaways) διατυπωμένα απλά και πρακτικά.
    3. Δημιούργησε 5 ουσιαστικές ερωτήσεις πολλαπλής επιλογής (4 επιλογές η καθεμία) με απλή επεξήγηση.
    """

    raw_json = _call_with_resilient_retry(
        contents=f"ΣΗΜΕΙΩΣΕΙΣ:\n{trimmed_notes}",
        system_instruction=system_instruction,
        schema=StudyGuideResponse,
        temperature=0.3,
    )
    result = StudyGuideResponse.model_validate_json(raw_json)
    result.extracted_text = trimmed_notes
    return result


def answer_voice_question(notes_text: str, question: str) -> VoiceAnswerResponse:
    """Απαντά απλοϊκά και προφορικά σε ερώτηση του φοιτητή πάνω στις σημειώσεις."""
    trimmed_notes = notes_text[:9000]

    system_instruction = """
    Είσαι ένας φιλικός καθηγητής που κάνει ιδιαίτερο μάθημα προφορικά στα Ελληνικά.
    Ο μαθητής σε διέκοψε για να σου κάνει μια ερώτηση πάνω στο μάθημα.
    Απάντησε ΠΟΛΥ ΑΠΛΟΪΚΑ, ζεστά και κατανοητά (σε 3 έως 5 σύντομες προτάσεις), με ένα μικρό καθημερινό παράδειγμα αν βοηθάει.
    ΜΗΝ χρησιμοποιείς αστεράκια (**), bullets (-), σύμβολα κώδικα ή markdown, γιατί το κείμενο θα διαβαστεί δυνατά με φωνή!
    """

    raw_json = _call_with_resilient_retry(
        contents=f"ΥΛΗ ΜΑΘΗΜΑΤΟΣ:\n{trimmed_notes}\n\nΕΡΩΤΗΣΗ ΜΑΘΗΤΗ:\n{question}",
        system_instruction=system_instruction,
        schema=VoiceAnswerResponse,
        temperature=0.35,
    )
    return VoiceAnswerResponse.model_validate_json(raw_json)


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
    Δημιούργησε 5 ΝΕΕΣ ερωτήσεις πολλαπλής επιλογής (4 επιλογές η καθεμία, με απλή επεξήγηση) στα Ελληνικά.
    """

    raw_json = _call_with_resilient_retry(
        contents=f"ΣΗΜΕΙΩΣΕΙΣ:\n{trimmed_notes}\n{avoid_block}",
        system_instruction=system_instruction,
        schema=NewQuizResponse,
        temperature=0.4,
    )
    return NewQuizResponse.model_validate_json(raw_json)