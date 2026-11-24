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
    http_options=types.HttpOptions(timeout=45000, api_version="v1beta"),
)


def _discover_available_models() -> list[str]:
    """Βρίσκει αυτόματα τα ενεργά και σταθερά Gemini μοντέλα που υποστηρίζουν generateContent."""
    fallback = [
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
        "gemini-3-flash-preview",
        "gemini-3.1-flash-lite-preview",
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
            ]
            ordered = [m for m in priority if m in pool]
            for m in sorted(pool, reverse=True):
                if m not in ordered:
                    ordered.append(m)

            print(f"✅ Διαθέσιμα Gemini μοντέλα: {ordered[:5]}", flush=True)
            return ordered[:5]
    except Exception as e:
        print(f"⚠️ Αδυναμία ανάκτησης λίστας μοντέλων ({e}), χρήση fallback.", flush=True)

    return fallback


ACTIVE_MODELS = _discover_available_models()


class StudySection(BaseModel):
    heading: str = Field(description="Απλός, ξεκάθαρος τίτλος της ενότητας")
    explanation: str = Field(
        description="Πολύ απλοϊκή, κατανοητή επεξήγηση σε φιλικό τόνο (2 σύντομες παράγραφοι), σαν να τα εξηγείς προφορικά σε έναν φίλο"
    )
    example: str = Field(description="Ένα καθημερινό, ρεαλιστικό παράδειγμα ή αναλογία")


class QuizQuestion(BaseModel):
    question: str = Field(description="Ερώτηση κατανόησης πάνω στις σημειώσεις")
    options: list[str] = Field(description="4 επιλογές απάντησης")
    correct_index: int = Field(description="Δείκτης 0-3 της σωστής απάντησης")
    explanation: str = Field(description="Σύντομη, απλή επεξήγηση γιατί αυτή είναι η σωστή απάντηση")


class StudyGuideResponse(BaseModel):
    title: str = Field(description="Γενικός τίτλος του κεφαλαίου")
    sections: list[StudySection] = Field(
        description="3 αναλυτικές, πολύ κατανοητές ενότητες θεωρίας με επεξηγήσεις και παραδείγματα"
    )
    key_takeaways: list[str] = Field(description="3 έως 4 βασικά συμπεράσματα-κλειδιά με απλά λόγια")
    quiz: list[QuizQuestion] = Field(description="5 ερωτήσεις πολλαπλής επιλογής")
    extracted_text: str = Field(default="", description="Το κείμενο των σημειώσεων")


class VoiceAnswerResponse(BaseModel):
    answer: str = Field(
        description="Πολύ απλοϊκή, προφορική απάντηση 3-4 προτάσεων στα Ελληνικά, χωρίς markdown, έτοιμη να διαβαστεί δυνατά"
    )


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """Διαβάζει γρήγορα κείμενο από PDF ή αρχείο κειμένου απευθείας από τη μνήμη (RAM)."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        pages_text = []
        total_chars = 0
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc[:12]:
                txt = page.get_text()
                pages_text.append(txt)
                total_chars += len(txt)
                if total_chars > 7000:
                    break
        return "\n\n".join(pages_text).strip()
    return file_bytes[:30000].decode("utf-8", errors="ignore").strip()


def _fast_generate_config(model_name: str, system_instruction: str, schema, temperature: float):
    kwargs = {
        "system_instruction": system_instruction,
        "response_mime_type": "application/json",
        "response_schema": schema,
        "temperature": temperature,
        "max_output_tokens": 4500,
    }
    if "flash" in model_name.lower() and "lite" not in model_name.lower():
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    return types.GenerateContentConfig(**kwargs)


def _call_with_resilient_retry(contents: str, system_instruction: str, schema, temperature: float) -> str:
    """Γρήγορη εναλλαγή διαθέσιμων μοντέλων με έλεγχο πλήρους JSON."""
    global ACTIVE_MODELS
    if not ACTIVE_MODELS:
        ACTIVE_MODELS = _discover_available_models()

    last_error = None
    max_rounds = 2

    for round_idx in range(1, max_rounds + 1):
        for model_name in ACTIVE_MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=_fast_generate_config(model_name, system_instruction, schema, temperature),
                )
                if response and response.text:
                    text = response.text.strip()
                    # Επαλήθευση ότι το JSON έκλεισε κανονικά και δεν κόπηκε στη μέση
                    schema.model_validate_json(text)
                    return text
            except Exception as e:
                last_error = e
                err_str = str(e)
                print(
                    f"⚠️ [Γύρος {round_idx}/{max_rounds}] {model_name}: {type(e).__name__} -> {err_str[:220]}",
                    flush=True,
                )

                if "404" in err_str or "NOT_FOUND" in err_str or "400" in err_str or "INVALID_ARGUMENT" in err_str:
                    continue

                if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    time.sleep(0.4 * round_idx + random.uniform(0.05, 0.2))
                    continue

        if round_idx < max_rounds:
            time.sleep(0.6)

    raise RuntimeError(
        f"Σφάλμα επικοινωνίας με Gemini API (μοντέλα: {ACTIVE_MODELS}): {last_error}"
    ) from last_error


def generate_study_guide_and_quiz(notes_text: str) -> StudyGuideResponse:
    """Παράγει γρήγορα απλοϊκό, επεξηγηματικό οδηγό και διαδραστικό Quiz."""
    trimmed_notes = notes_text[:6500]

    system_instruction = """
    Είσαι ένας μεταδοτικός καθηγητής. Εξήγησε την ύλη στα Ελληνικά με ΠΟΛΥ ΑΠΛΑ, καθημερινά λόγια (χωρίς δύσκολη ορολογία):
    1. Χώρισε την ύλη σε 3 λογικές ενότητες (sections). Για κάθε ενότητα δώσε:
       - Απλή, ζωντανή επεξήγηση (2 σύντομες παράγραφοι) που απαντά στο "τι πρόβλημα λύνει;" και "πώς δουλεύει;".
       - Ένα καθημερινό παράδειγμα (π.χ. μαγειρική, οδήγηση, ψώνια).
    2. Δώσε 3-4 απλά συμπεράσματα-κλειδιά (key_takeaways).
    3. Δημιούργησε 5 ερωτήσεις πολλαπλής επιλογής (4 επιλογές η καθεμία) με σύντομη, απλή επεξήγηση.
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
    trimmed_notes = notes_text[:6500]

    system_instruction = """
    Είσαι ένας φιλικός καθηγητής που κάνει ιδιαίτερο μάθημα προφορικά στα Ελληνικά.
    Απάντησε ΠΟΛΥ ΑΠΛΟΪΚΑ και κατανοητά (σε 3 έως 4 σύντομες προτάσεις), με ένα μικρό καθημερινό παράδειγμα.
    ΜΗΝ χρησιμοποιείς αστεράκια (**), bullets (-), σύμβολα κώδικα ή markdown!
    """

    raw_json = _call_with_resilient_retry(
        contents=f"ΥΛΗ:\n{trimmed_notes}\n\nΕΡΩΤΗΣΗ:\n{question}",
        system_instruction=system_instruction,
        schema=VoiceAnswerResponse,
        temperature=0.35,
    )
    return VoiceAnswerResponse.model_validate_json(raw_json)


class NewQuizResponse(BaseModel):
    quiz: list[QuizQuestion] = Field(description="5 νέες ερωτήσεις πολλαπλής επιλογής")


def generate_new_quiz(notes_text: str, previous_questions: list[str] = None) -> NewQuizResponse:
    """Παράγει ένα νέο σετ 5 ερωτήσεων."""
    trimmed_notes = notes_text[:6500]
    avoid_block = ""
    if previous_questions:
        joined = "\n".join(f"- {q}" for q in previous_questions)
        avoid_block = f"\nΜΗΝ επαναλάβεις:\n{joined}\n"

    system_instruction = """
    Δημιούργησε 5 ΝΕΕΣ ερωτήσεις πολλαπλής επιλογής (4 επιλογές η καθεμία, με σύντομη επεξήγηση) στα Ελληνικά.
    """

    raw_json = _call_with_resilient_retry(
        contents=f"ΣΗΜΕΙΩΣΕΙΣ:\n{trimmed_notes}\n{avoid_block}",
        system_instruction=system_instruction,
        schema=NewQuizResponse,
        temperature=0.4,
    )
    return NewQuizResponse.model_validate_json(raw_json)