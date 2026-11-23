from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse

from rag_engine import (
    extract_text_from_bytes,
    generate_study_guide_and_quiz,
    StudyGuideResponse,
)

app = FastAPI(title="AI Study Explainer & Quiz Generator")


@app.post("/api/study", response_model=StudyGuideResponse)
async def api_study(
    notes_text: str = Form(""),
    file: Optional[UploadFile] = File(None),
):
    combined_text = notes_text.strip()

    if file and file.filename:
        file_bytes = await file.read()
        if file_bytes:
            extracted = extract_text_from_bytes(file_bytes, file.filename)
            combined_text = f"{combined_text}\n\n{extracted}".strip() if combined_text else extracted

    if len(combined_text) < 20:
        raise HTTPException(
            status_code=400,
            detail="Πρόσθεσε λίγο περισσότερο κείμενο σημειώσεων ή ανέβασε ένα αρχείο (.pdf, .txt, .py).",
        )

    try:
        return generate_study_guide_and_quiz(combined_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
def serve_ui():
    return """
<!DOCTYPE html>
<html lang="el">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Study Explainer & Quiz Generator</title>
    <style>
        :root {
            --bg: #0f172a;
            --card: #1e293b;
            --card-inner: #0f172a;
            --border: #334155;
            --text: #f8fafc;
            --muted: #94a3b8;
            --accent: #38bdf8;
            --accent-hover: #0284c7;
            --success: #22c55e;
            --danger: #ef4444;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, sans-serif; }
        body { background: var(--bg); color: var(--text); min-height: 100vh; padding-bottom: 60px; }
        header {
            padding: 18px 24px; background: var(--card); border-bottom: 1px solid var(--border);
            display: flex; justify-content: space-between; align-items: center;
        }
        header h1 { font-size: 1.25rem; display: flex; align-items: center; gap: 10px; }
        .badge { font-size: 0.75rem; background: rgba(56, 189, 248, 0.15); color: var(--accent); padding: 4px 10px; border-radius: 999px; border: 1px solid rgba(56, 189, 248, 0.3); }
        .container { max-width: 880px; margin: 28px auto; padding: 0 20px; display: flex; flex-direction: column; gap: 24px; }
        .panel { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 22px; }
        .panel-title { font-size: 1rem; font-weight: 600; margin-bottom: 12px; color: var(--accent); display: flex; justify-content: space-between; align-items: center; }
        textarea {
            width: 100%; min-height: 150px; padding: 14px; border-radius: 10px;
            border: 1px solid var(--border); background: var(--card-inner); color: var(--text);
            font-size: 0.98rem; line-height: 1.5; resize: vertical; outline: none;
        }
        textarea:focus { border-color: var(--accent); }
        .controls { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 14px; }
        .file-label {
            display: inline-flex; align-items: center; gap: 8px; padding: 9px 14px;
            background: var(--card-inner); border: 1px dashed var(--border); border-radius: 8px;
            cursor: pointer; font-size: 0.9rem; color: var(--muted); transition: 0.2s;
        }
        .file-label:hover { border-color: var(--accent); color: var(--text); }
        button.primary {
            background: var(--accent); color: #0f172a; font-weight: 700; border: none;
            padding: 11px 22px; border-radius: 8px; cursor: pointer; font-size: 0.95rem; transition: 0.2s;
        }
        button.primary:hover { background: var(--accent-hover); color: white; }
        button.primary:disabled { opacity: 0.5; cursor: not-allowed; }
        button.submit-quiz-btn {
            background: var(--success); color: #052e16; font-weight: 700; border: none;
            padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 0.98rem;
            margin-top: 18px; width: 100%; transition: 0.2s;
        }
        button.submit-quiz-btn:hover { background: #16a34a; color: white; }
        button.submit-quiz-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .demo-link { font-size: 0.82rem; color: var(--accent); cursor: pointer; text-decoration: underline; background: none; border: none; }
        .explanation-text { line-height: 1.75; font-size: 1.02rem; white-space: pre-wrap; color: #e2e8f0; }
        .takeaways { margin-top: 18px; padding-top: 16px; border-top: 1px solid var(--border); }
        .takeaways h3 { font-size: 0.92rem; text-transform: uppercase; color: var(--muted); margin-bottom: 10px; }
        .takeaways ul { list-style: none; display: flex; flex-direction: column; gap: 8px; }
        .takeaways li { background: rgba(15, 23, 42, 0.5); padding: 10px 14px; border-radius: 8px; border-left: 3px solid var(--accent); font-size: 0.95rem; }
        .quiz-card { background: var(--card-inner); border: 1px solid var(--border); border-radius: 12px; padding: 18px; margin-top: 14px; }
        .quiz-q { font-weight: 600; font-size: 1rem; margin-bottom: 12px; }
        .options { display: flex; flex-direction: column; gap: 8px; }
        .option-btn {
            text-align: left; padding: 11px 14px; border-radius: 8px; border: 1px solid var(--border);
            background: var(--card); color: var(--text); cursor: pointer; font-size: 0.94rem; transition: 0.15s;
        }
        .option-btn:hover:not(:disabled) { border-color: var(--accent); background: rgba(56, 189, 248, 0.08); }
        .option-btn.selected {
            border-color: var(--accent);
            background: rgba(56, 189, 248, 0.2);
            color: #e0f2fe;
            font-weight: 600;
        }
        .option-btn.correct { background: rgba(34, 197, 94, 0.22); border-color: var(--success); color: #bbf7d0; font-weight: 600; }
        .option-btn.wrong { background: rgba(239, 68, 68, 0.22); border-color: var(--danger); color: #fecaca; }
        .quiz-feedback { margin-top: 10px; font-size: 0.9rem; color: var(--muted); padding: 10px 12px; border-radius: 8px; background: rgba(255,255,255,0.04); display: none; }
        .score-pill { background: rgba(34, 197, 94, 0.15); color: var(--success); padding: 4px 12px; border-radius: 999px; font-size: 0.85rem; }
    </style>
</head>
<body>
    <header>
        <h1>🧠 AI Study Explainer & Quiz <span class="badge">Instant Comprehension</span></h1>
    </header>

    <div class="container">
        <div class="panel">
            <div class="panel-title">
                <span>1. Επικόλλησε τις σημειώσεις σου ή ανέβασε αρχείο</span>
                <button type="button" class="demo-link" onclick="fillDemoNotes()">Γέμισμα με παράδειγμα σημειώσεων</button>
            </div>
            <textarea id="notes-input" placeholder="Γράψε ή κάνε επικόλληση (Ctrl+V) τις σημειώσεις σου εδώ..."></textarea>

            <div class="controls">
                <label class="file-label">
                    📎 <span id="file-name">Προαιρετικά: Ανέβασε .pdf, .txt ή .py</span>
                    <input type="file" id="file-input" accept=".pdf,.txt,.py,.md" style="display:none" onchange="updateFileName()">
                </label>
                <button class="primary" id="generate-btn" onclick="generateStudy()">✨ Εξήγηση & Δημιουργία Quiz</button>
            </div>
        </div>

        <div id="results-area" style="display:none; flex-direction: column; gap: 24px;">
            <div class="panel">
                <div class="panel-title" id="result-title">📖 Απλή Επεξήγηση</div>
                <div class="explanation-text" id="explanation-box"></div>
                <div class="takeaways">
                    <h3>🔑 Βασικά Σημεία-Κλειδιά</h3>
                    <ul id="takeaways-list"></ul>
                </div>
            </div>

            <div class="panel">
                <div class="panel-title">
                    <span>🎯 Quiz Αυτοαξιολόγησης</span>
                    <span class="score-pill" id="score-display">Επιλεγμένα: 0 / 0</span>
                </div>
                <div id="quiz-container"></div>
                <button class="submit-quiz-btn" id="submit-quiz-btn" onclick="submitQuiz()">✅ Υποβολή Quiz & Έλεγχος Αποτελεσμάτων</button>
            </div>
        </div>
    </div>

    <script>
        let currentQuizData = [];
        let userSelections = {};
        let isSubmitted = false;

        function updateFileName() {
            const input = document.getElementById('file-input');
            const label = document.getElementById('file-name');
            label.textContent = input.files.length ? input.files[0].name : 'Προαιρετικά: Ανέβασε .pdf, .txt ή .py';
        }

        function fillDemoNotes() {
            document.getElementById('notes-input').value =
`Το Gradient Descent (Κατάβαση Κλίσης) είναι ο βασικός αλγόριθμος βελτιστοποίησης στη Μηχανική Μάθηση. Σκοπός του είναι να ελαχιστοποιήσει τη συνάρτηση κόστους (Loss Function), η