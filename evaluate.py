import time
import json
from pydantic import BaseModel, Field
from rag_engine import ask_notes, generate_with_retry


class EvalScore(BaseModel):
    faithfulness: int = Field(description="Βαθμολογία 1-5: Κατά πόσο η απάντηση βασίζεται αυστηρά στις σημειώσεις χωρίς επινοήσεις")
    relevance: int = Field(description="Βαθμολογία 1-5: Κατά πόσο η απάντηση απαντά ουσιαστικά στην ερώτηση")
    hallucination_guard_passed: bool = Field(description="True αν το σύστημα χειρίστηκε σωστά τόσο τις εντός ύλης όσο και τις εκτός ύλης ερωτήσεις")
    reasoning: str = Field(description="Σύντομη αιτιολόγηση 1 πρότασης")


TEST_CASES = [
    {
        "question": "Τι αναφέρουν οι σημειώσεις για τη βιβλιοθήκη Pandas;",
        "expected_in_notes": True,
    },
    {
        "question": "Ποιες βασικές έννοιες ή τεχνικές αναλύονται στα αρχεία του μαθήματος;",
        "expected_in_notes": True,
    },
    {
        "question": "Ποια είναι η παραδοσιακή συνταγή για μουσακά;",
        "expected_in_notes": False,
    },
]


def judge_response(question: str, expected_in_notes: bool, rag_result) -> EvalScore:
    judge_prompt = f"""
    Αξιολόγησε την παρακάτω απόκριση ενός RAG συστήματος:
    - Ερώτηση: {question}
    - Έπρεπε η απάντηση να βρεθεί στις σημειώσεις; {expected_in_notes}
    - Το σύστημα δήλωσε found_in_notes: {rag_result.found_in_notes}
    - Απάντηση συστήματος: {rag_result.answer}
    - Citations που επέστρεψε: {[c.model_dump() for c in rag_result.citations]}
    """
    print("   ⚖️ Judge αξιολόγηση...", flush=True)
    raw_json = generate_with_retry(
        prompt=judge_prompt,
        system_instruction="Είσαι αυστηρός LLM-as-a-Judge αξιολογητής RAG συστημάτων.",
        response_schema=EvalScore,
    )
    return EvalScore.model_validate_json(raw_json)


def run_evaluation():
    print("🧪 Εκκίνηση Automated RAG Evaluation (LLM-as-a-Judge)...\n", flush=True)
    results_summary = []

    for idx, tc in enumerate(TEST_CASES, start=1):
        print(f"--- Test {idx}/{len(TEST_CASES)}: {tc['question']} ---", flush=True)
        start_time = time.time()
        rag_out = ask_notes(tc["question"])
        latency = round(time.time() - start_time, 2)

        score = judge_response(tc["question"], tc["expected_in_notes"], rag_out)
        results_summary.append({
            "test_id": idx,
            "question": tc["question"],
            "latency_sec": latency,
            "found_in_notes": rag_out.found_in_notes,
            "expected": tc["expected_in_notes"],
            "faithfulness": score.faithfulness,
            "relevance": score.relevance,
            "guard_passed": score.hallucination_guard_passed,
            "reasoning": score.reasoning,
        })
        print(f"✅ Αποτέλεσμα Test {idx} | Latency: {latency}s | Faithfulness: {score.faithfulness}/5 | Relevance: {score.relevance}/5 | Guard: {score.hallucination_guard_passed}\n", flush=True)

    with open("eval_report.json", "w", encoding="utf-8") as f:
        json.dump(results_summary, f, ensure_ascii=False, indent=2)

    print("📊 Η αναφορά αποθηκεύτηκε στο eval_report.json!", flush=True)


if __name__ == "__main__":
    run_evaluation()