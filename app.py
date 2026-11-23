from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from rag_engine import (
    extract_text_from_bytes,
    generate_study_guide_and_quiz,
    generate_new_quiz,
    StudyGuideResponse,
    NewQuizResponse,
)

app = FastAPI(title="AI Study Explainer & Quiz Generator")


class NewQuizRequest(BaseModel):
    notes_text: str
    previous_questions: list[str] = []


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


@app.post("/api/new-quiz", response_model=NewQuizResponse)
def api_new_quiz(payload: NewQuizRequest):
    if len(payload.notes_text.strip()) < 20:
        raise HTTPException(status_code=400, detail="Δεν βρέθηκαν σημειώσεις για νέο quiz.")
    try:
        return generate_new_quiz(payload.notes_text, payload.previous_questions)
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
    <title>AI Study Studio — Explainer & Quiz</title>
    <style>
        :root {
            --bg: #0b0f19;
            --surface: #131a2a;
            --surface-elevated: #192236;
            --border: #25324b;
            --text: #f1f5f9;
            --muted: #94a3b8;

            /* Νέα παλέτα: Indigo για δράσεις/Quiz, Amber για Summary, Emerald για Επιτυχία */
            --primary: #6366f1;
            --primary-light: #818cf8;
            --primary-hover: #4f46e5;
            --summary-accent: #f59e0b;
            --summary-bg: rgba(245, 158, 11, 0.08);
            --quiz-accent: #818cf8;
            --quiz-bg: rgba(99, 102, 241, 0.08);
            --success: #10b981;
            --danger: #f43f5e;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', 'Segoe UI', system-ui, sans-serif; }
        body { background: var(--bg); color: var(--text); min-height: 100vh; padding-bottom: 70px; }

        header {
            padding: 16px 28px;
            background: rgba(19, 26, 42, 0.9);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 20;
        }
        header h1 { font-size: 1.2rem; font-weight: 700; display: flex; align-items: center; gap: 10px; letter-spacing: -0.01em; }
        .badge {
            font-size: 0.72rem;
            background: rgba(99, 102, 241, 0.16);
            color: var(--primary-light);
            padding: 4px 11px;
            border-radius: 999px;
            border: 1px solid rgba(129, 140, 248, 0.35);
            font-weight: 600;
        }
        .header-reset-btn {
            display: none;
            background: var(--surface-elevated);
            color: var(--text);
            border: 1px solid var(--border);
            padding: 7px 14px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: 0.2s;
        }
        .header-reset-btn:hover { border-color: var(--primary-light); color: var(--primary-light); }

        .container { max-width: 900px; margin: 32px auto; padding: 0 20px; display: flex; flex-direction: column; gap: 28px; }

        /* Input Panel */
        .input-panel {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 26px;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
        }
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
            gap: 12px;
        }
        .panel-title { font-size: 1.05rem; font-weight: 600; color: var(--text); }
        textarea {
            width: 100%;
            min-height: 170px;
            padding: 16px;
            border-radius: 12px;
            border: 1px solid var(--border);
            background: var(--bg);
            color: var(--text);
            font-size: 0.98rem;
            line-height: 1.6;
            resize: vertical;
            outline: none;
            transition: 0.2s;
        }
        textarea:focus { border-color: var(--primary-light); box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15); }
        .controls { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px; margin-top: 16px; }
        .file-label {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 16px;
            background: var(--bg);
            border: 1px dashed var(--border);
            border-radius: 10px;
            cursor: pointer;
            font-size: 0.9rem;
            color: var(--muted);
            transition: 0.2s;
        }
        .file-label:hover { border-color: var(--primary-light); color: var(--text); }

        button.primary {
            background: linear-gradient(135deg, var(--primary), var(--primary-hover));
            color: white;
            font-weight: 600;
            border: none;
            padding: 12px 24px;
            border-radius: 10px;
            cursor: pointer;
            font-size: 0.96rem;
            box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
            transition: 0.2s;
        }
        button.primary:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(99, 102, 241, 0.45); }
        button.primary:disabled { opacity: 0.55; cursor: not-allowed; transform: none; }

        .demo-link { font-size: 0.84rem; color: var(--primary-light); cursor: pointer; text-decoration: none; background: none; border: none; font-weight: 500; }
        .demo-link:hover { text-decoration: underline; }

        /* --- SECTION 1: SUMMARY CARD (Θερμό Amber / Study Guide Look) --- */
        .summary-panel {
            background: linear-gradient(180deg, rgba(245, 158, 11, 0.06) 0%, var(--surface) 140px);
            border: 1px solid rgba(245, 158, 11, 0.3);
            border-left: 5px solid var(--summary-accent);
            border-radius: 16px;
            padding: 26px;
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.28);
        }
        .section-tag {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            padding: 4px 10px;
            border-radius: 6px;
            margin-bottom: 10px;
        }
        .tag-summary { background: rgba(245, 158, 11, 0.16); color: #fbbf24; }
        .tag-quiz { background: rgba(99, 102, 241, 0.18); color: #a5b4fc; }

        .summary-title { font-size: 1.35rem; font-weight: 700; color: #fef3c7; margin-bottom: 16px; }
        .explanation-text {
            line-height: 1.8;
            font-size: 1.02rem;
            white-space: pre-wrap;
            color: #e2e8f0;
            background: rgba(11, 15, 25, 0.45);
            padding: 18px;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        .takeaways { margin-top: 22px; }
        .takeaways h3 { font-size: 0.88rem; text-transform: uppercase; letter-spacing: 0.05em; color: #fbbf24; margin-bottom: 12px; }
        .takeaways-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; }
        .takeaway-item {
            background: var(--surface-elevated);
            padding: 12px 15px;
            border-radius: 10px;
            border: 1px solid var(--border);
            border-left: 3px solid var(--summary-accent);
            font-size: 0.93rem;
            line-height: 1.5;
            color: #f8fafc;
        }

        /* --- SECTION 2: QUIZ ARENA (Indigo / Violet Interactive Look) --- */
        .quiz-panel {
            background: linear-gradient(180deg, rgba(99, 102, 241, 0.07) 0%, var(--surface) 140px);
            border: 1px solid rgba(129, 140, 248, 0.35);
            border-top: 4px solid var(--primary);
            border-radius: 16px;
            padding: 26px;
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.28);
        }
        .quiz-header-row {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 18px;
        }
        .quiz-main-title { font-size: 1.3rem; font-weight: 700; color: #e0e7ff; }
        .score-pill {
            background: rgba(99, 102, 241, 0.18);
            color: #c7d2fe;
            border: 1px solid rgba(129, 140, 248, 0.35);
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 0.88rem;
            font-weight: 600;
        }
        .score-pill.completed {
            background: rgba(16, 185, 129, 0.18);
            color: #6ee7b7;
            border-color: rgba(16, 185, 129, 0.4);
        }

        .quiz-card {
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 20px;
            margin-top: 16px;
        }
        .quiz-q {
            font-weight: 600;
            font-size: 1.02rem;
            margin-bottom: 14px;
            display: flex;
            align-items: flex-start;
            gap: 10px;
            line-height: 1.5;
        }
        .q-num {
            background: var(--primary);
            color: white;
            font-size: 0.8rem;
            font-weight: 700;
            min-width: 26px;
            height: 26px;
            border-radius: 8px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-top: 2px;
        }
        .options { display: flex; flex-direction: column; gap: 9px; }
        .option-btn {
            text-align: left;
            padding: 12px 16px;
            border-radius: 10px;
            border: 1px solid var(--border);
            background: var(--surface);
            color: var(--text);
            cursor: pointer;
            font-size: 0.95rem;
            transition: 0.15s;
        }
        .option-btn:hover:not(:disabled) { border-color: var(--primary-light); background: var(--surface-elevated); }
        .option-btn.selected {
            border-color: var(--primary-light);
            background: rgba(99, 102, 241, 0.22);
            color: #eef2ff;
            font-weight: 600;
        }
        .option-btn.correct { background: rgba(16, 185, 129, 0.2); border-color: var(--success); color: #a7f3d0; font-weight: 600; }
        .option-btn.wrong { background: rgba(244, 63, 94, 0.2); border-color: var(--danger); color: #fecdd3; }

        .quiz-feedback {
            margin-top: 12px;
            font-size: 0.92rem;
            color: #cbd5e1;
            padding: 12px 14px;
            border-radius: 10px;
            background: var(--surface-elevated);
            border-left: 3px solid var(--primary-light);
            display: none;
            line-height: 1.5;
        }

        button.submit-quiz-btn {
            background: linear-gradient(135deg, var(--success), #059669);
            color: white;
            font-weight: 700;
            border: none;
            padding: 14px 24px;
            border-radius: 10px;
            cursor: pointer;
            font-size: 1rem;
            margin-top: 22px;
            width: 100%;
            box-shadow: 0 4px 14px rgba(16, 185, 129, 0.3);
            transition: 0.2s;
        }
        button.submit-quiz-btn:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4); }
        button.submit-quiz-btn:disabled { opacity: 0.5; cursor: not-allowed; }

        /* Next Steps Card */
        .next-steps-box {
            margin-top: 24px;
            padding: 22px;
            border-radius: 14px;
            background: var(--surface-elevated);
            border: 1px solid var(--primary-light);
            display: none;
            flex-direction: column;
            gap: 16px;
        }
        .next-steps-msg { font-size: 1.03rem; line-height: 1.6; color: var(--text); }
        .next-steps-actions { display: flex; flex-wrap: wrap; gap: 10px; }
        .action-btn {
            padding: 11px 18px;
            border-radius: 10px;
            font-weight: 600;
            font-size: 0.92rem;
            cursor: pointer;
            border: 1px solid var(--border);
            transition: 0.2s;
        }
        .btn-retry { background: rgba(245, 158, 11, 0.16); color: #fcd34d; border-color: rgba(245, 158, 11, 0.4); }
        .btn-retry:hover { background: rgba(245, 158, 11, 0.28); }
        .btn-new-quiz { background: rgba(99, 102, 241, 0.18); color: #c7d2fe; border-color: rgba(129, 140, 248, 0.45); }
        .btn-new-quiz:hover { background: rgba(99, 102, 241, 0.32); }
        .btn-new-quiz:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-next-chapter { background: var(--primary); color: white; border: none; }
        .btn-next-chapter:hover { background: var(--primary-hover); }
    </style>
</head>
<body>
    <header>
        <h1>✨ AI Study Studio <span class="badge">Summary + Interactive Quiz</span></h1>
        <button class="header-reset-btn" id="header-new-notes-btn" onclick="startNextChapter()">📝 Νέες Σημειώσεις / Αρχείο</button>
    </header>

    <div class="container">
        <!-- INPUT PANEL (Κρύβεται αυτόματα μόλις φορτώσει το μάθημα) -->
        <div class="input-panel" id="input-panel">
            <div class="panel-header">
                <span class="panel-title">Επικόλλησε τις σημειώσεις σου ή ανέβασε αρχείο</span>
                <button type="button" class="demo-link" onclick="fillDemoNotes()">Γέμισμα με παράδειγμα σημειώσεων</button>
            </div>
            <textarea id="notes-input" placeholder="Γράψε ή κάνε επικόλληση (Ctrl+V) τις σημειώσεις σου εδώ..."></textarea>

            <div class="controls">
                <label class="file-label">
                    📎 <span id="file-name">Ανέβασε .pdf, .txt ή .py</span>
                    <input type="file" id="file-input" accept=".pdf,.txt,.py,.md" style="display:none" onchange="updateFileName()">
                </label>
                <button class="primary" id="generate-btn" onclick="generateStudy()">🚀 Ανάλυση & Δημιουργία Quiz</button>
            </div>
        </div>

        <!-- RESULTS AREA -->
        <div id="results-area" style="display:none; flex-direction: column; gap: 30px;">

            <!-- ENOTHTA 1: SUMMARY (Amber Theme) -->
            <section class="summary-panel">
                <span class="section-tag tag-summary">📖 Ενότητα 1 · Θεωρία & Σύνοψη</span>
                <h2 class="summary-title" id="result-title">Απλή Επεξήγηση</h2>
                <div class="explanation-text" id="explanation-box"></div>

                <div class="takeaways">
                    <h3>🔑 Βασικά Σημεία-Κλειδιά</h3>
                    <div class="takeaways-grid" id="takeaways-list"></div>
                </div>
            </section>

            <!-- ENOTHTA 2: QUIZ (Indigo Theme) -->
            <section class="quiz-panel">
                <div class="quiz-header-row">
                    <div>
                        <span class="section-tag tag-quiz">🎯 Ενότητα 2 · Εξάσκηση</span>
                        <h2 class="quiz-main-title">Quiz Αυτοαξιολόγησης</h2>
                    </div>
                    <span class="score-pill" id="score-display">Επιλεγμένα: 0 / 0</span>
                </div>

                <div id="quiz-container"></div>
                <button class="submit-quiz-btn" id="submit-quiz-btn" onclick="submitQuiz()">✅ Υποβολή Quiz & Έλεγχος Αποτελεσμάτων</button>

                <div class="next-steps-box" id="next-steps-box">
                    <div class="next-steps-msg" id="next-steps-msg"></div>
                    <div class="next-steps-actions">
                        <button class="action-btn btn-retry" id="retry-btn" onclick="retryCurrentQuiz()">🔄 Επανάληψη ίδιου Quiz</button>
                        <button class="action-btn btn-new-quiz" id="new-quiz-btn" onclick="requestNewQuiz()">🎲 Νέο Quiz (νέες ερωτήσεις)</button>
                        <button class="action-btn btn-next-chapter" onclick="startNextChapter()">📚 Επόμενο Κεφάλαιο (νέες σημειώσεις)</button>
                    </div>
                </div>
            </section>

        </div>
    </div>

    <script>
        let currentQuizData = [];
        let userSelections = {};
        let isSubmitted = false;
        let activeNotesText = "";

        function updateFileName() {
            const input = document.getElementById('file-input');
            const label = document.getElementById('file-name');
            label.textContent = input.files.length ? input.files[0].name : 'Ανέβασε .pdf, .txt ή .py';
        }

        function fillDemoNotes() {
            document.getElementById('notes-input').value =
`Το Gradient Descent (Κατάβαση Κλίσης) είναι ο βασικός αλγόριθμος βελτιστοποίησης στη Μηχανική Μάθηση. Σκοπός του είναι να ελαχιστοποιήσει τη συνάρτηση κόστους (Loss Function), η οποία μετρά πόσο απέχουν οι προβλέψεις του μοντέλου από τις πραγματικές τιμές. Σε κάθε βήμα, υπολογίζει την παράγωγο (gradient) της συνάρτησης κόστους ως προς τα βάρη (weights) και ενημερώνει τα βάρη προς την αντίθετη κατεύθυνση της κλίσης. Το μέγεθος του βήματος καθορίζεται από το Learning Rate (ρυθμός μάθησης): αν είναι πολύ μεγάλο, ο αλγόριθμος μπορεί να αστοχήσει και να αποκλίνει· αν είναι πολύ μικρό, η εκπαίδευση γίνεται εξαιρετικά αργή.`;
        }

        async function generateStudy() {
            const notes = document.getElementById('notes-input').value.trim();
            const fileInput = document.getElementById('file-input');
            const btn = document.getElementById('generate-btn');

            if (!notes && !fileInput.files.length) {
                return alert('Γράψε/επικόλλησε σημειώσεις ή επίλεξε ένα αρχείο πρώτα!');
            }

            btn.disabled = true;
            btn.textContent = '⏳ Ανάλυση & σύνταξη Quiz...';

            const formData = new FormData();
            formData.append('notes_text', notes);
            if (fileInput.files.length) {
                formData.append('file', fileInput.files[0]);
            }

            try {
                const res = await fetch('/api/study', { method: 'POST', body: formData });
                const rawText = await res.text();
                let data;
                try { data = JSON.parse(rawText); }
                catch { throw new Error(`Σφάλμα διακομιστή (HTTP ${res.status}).`); }

                if (!res.ok) throw new Error(data.detail || 'Αποτυχία επεξήγησης');
                activeNotesText = data.extracted_text || notes;
                renderResults(data);
            } catch (err) {
                alert('❌ ' + err.message);
            } finally {
                btn.disabled = false;
                btn.textContent = '🚀 Ανάλυση & Δημιουργία Quiz';
            }
        }

        function renderResults(data) {
            // Κρύβουμε το πεδίο επικόλλησης/ανεβάσματος και δείχνουμε το κουμπί στο header
            document.getElementById('input-panel').style.display = 'none';
            document.getElementById('header-new-notes-btn').style.display = 'inline-block';

            document.getElementById('results-area').style.display = 'flex';
            document.getElementById('result-title').textContent = data.title;
            document.getElementById('explanation-box').textContent = data.simple_explanation;

            const list = document.getElementById('takeaways-list');
            list.innerHTML = data.key_takeaways.map(item => `<div class="takeaway-item">${item}</div>`).join('');

            renderQuizQuestions(data.quiz);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        function renderQuizQuestions(quizList) {
            currentQuizData = quizList;
            userSelections = {};
            isSubmitted = false;

            document.getElementById('next-steps-box').style.display = 'none';

            const scorePill = document.getElementById('score-display');
            scorePill.classList.remove('completed');

            const submitBtn = document.getElementById('submit-quiz-btn');
            submitBtn.disabled = false;
            submitBtn.style.display = 'block';
            submitBtn.textContent = '✅ Υποβολή Quiz & Έλεγχος Αποτελεσμάτων';

            updateSelectionCounter();

            const quizContainer = document.getElementById('quiz-container');
            quizContainer.innerHTML = '';

            currentQuizData.forEach((q, qIdx) => {
                const card = document.createElement('div');
                card.className = 'quiz-card';
                card.id = `quiz-card-${qIdx}`;

                const qTitle = document.createElement('div');
                qTitle.className = 'quiz-q';
                qTitle.innerHTML = `<span class="q-num">${qIdx + 1}</span><span>${q.question}</span>`;
                card.appendChild(qTitle);

                const optsDiv = document.createElement('div');
                optsDiv.className = 'options';

                q.options.forEach((optText, optIdx) => {
                    const optBtn = document.createElement('button');
                    optBtn.className = 'option-btn';
                    optBtn.textContent = optText;
                    optBtn.onclick = () => {
                        if (isSubmitted) return;
                        userSelections[qIdx] = optIdx;

                        const allBtns = optsDiv.querySelectorAll('button');
                        allBtns.forEach(b => b.classList.remove('selected'));
                        optBtn.classList.add('selected');

                        updateSelectionCounter();
                    };
                    optsDiv.appendChild(optBtn);
                });

                const feedback = document.createElement('div');
                feedback.className = 'quiz-feedback';
                feedback.id = `quiz-feedback-${qIdx}`;

                card.appendChild(optsDiv);
                card.appendChild(feedback);
                quizContainer.appendChild(card);
            });
        }

        function updateSelectionCounter() {
            const selectedCount = Object.keys(userSelections).length;
            document.getElementById('score-display').textContent = `Επιλεγμένα: ${selectedCount} / ${currentQuizData.length}`;
        }

        function submitQuiz() {
            const total = currentQuizData.length;
            const answeredCount = Object.keys(userSelections).length;

            if (answeredCount < total) {
                const proceed = confirm(`Έχεις απαντήσει σε ${answeredCount} από τις ${total} ερωτήσεις. Θέλεις να υποβάλεις το Quiz τώρα;`);
                if (!proceed) return;
            }

            isSubmitted = true;
            let score = 0;

            currentQuizData.forEach((q, qIdx) => {
                const card = document.getElementById(`quiz-card-${qIdx}`);
                const allBtns = card.querySelectorAll('.option-btn');
                const feedback = document.getElementById(`quiz-feedback-${qIdx}`);
                const chosenIdx = userSelections[qIdx];

                allBtns.forEach((btn, optIdx) => {
                    btn.disabled = true;
                    btn.classList.remove('selected');

                    if (optIdx === q.correct_index) {
                        btn.classList.add('correct');
                    } else if (optIdx === chosenIdx && chosenIdx !== q.correct_index) {
                        btn.classList.add('wrong');
                    }
                });

                if (chosenIdx === q.correct_index) {
                    score++;
                    feedback.innerHTML = `✅ <strong>Σωστό!</strong> ${q.explanation}`;
                } else if (chosenIdx === undefined) {
                    feedback.innerHTML = `⚠️ <strong>Δεν απαντήθηκε.</strong> Σωστή απάντηση: <em>${q.options[q.correct_index]}</em>. ${q.explanation}`;
                } else {
                    feedback.innerHTML = `❌ <strong>Λάθος.</strong> ${q.explanation}`;
                }
                feedback.style.display = 'block';
            });

            const scorePill = document.getElementById('score-display');
            scorePill.textContent = `Τελικό Σκορ: ${score} / ${total}`;
            scorePill.classList.add('completed');

            const submitBtn = document.getElementById('submit-quiz-btn');
            submitBtn.style.display = 'none';

            const nextBox = document.getElementById('next-steps-box');
            const nextMsg = document.getElementById('next-steps-msg');
            const retryBtn = document.getElementById('retry-btn');

            if (score === total) {
                nextMsg.innerHTML = `🎉 <strong>Άριστα! Τα απάντησες όλα σωστά (${score}/${total})!</strong><br>Θέλεις να εξασκηθείς με ένα <strong>νέο quiz</strong> πάνω στις ίδιες σημειώσεις ή να προχωρήσουμε στο <strong>επόμενο κεφάλαιο</strong>;`;
                retryBtn.style.display = 'none';
            } else {
                nextMsg.innerHTML = `💡 <strong>Πέτυχες ${score} στα ${total}!</strong><br>Θέλεις να <strong>ξανακάνεις το ίδιο quiz</strong> για να διορθώσεις τα λάθη σου, να δοκιμάσεις ένα <strong>νέο quiz</strong> ή να προχωρήσουμε στο <strong>επόμενο κεφάλαιο</strong>;`;
                retryBtn.style.display = 'inline-block';
            }

            nextBox.style.display = 'flex';
            nextBox.scrollIntoView({ behavior: 'smooth' });
        }

        function retryCurrentQuiz() {
            renderQuizQuestions(currentQuizData);
            document.getElementById('quiz-container').scrollIntoView({ behavior: 'smooth' });
        }

        async function requestNewQuiz() {
            const btn = document.getElementById('new-quiz-btn');
            btn.disabled = true;
            btn.textContent = '⏳ Δημιουργία νέων ερωτήσεων...';

            try {
                const res = await fetch('/api/new-quiz', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        notes_text: activeNotesText,
                        previous_questions: currentQuizData.map(q => q.question)
                    })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Αποτυχία δημιουργίας νέου quiz');

                renderQuizQuestions(data.quiz);
                document.getElementById('quiz-container').scrollIntoView({ behavior: 'smooth' });
            } catch (err) {
                alert('❌ ' + err.message);
            } finally {
                btn.disabled = false;
                btn.textContent = '🎲 Νέο Quiz (νέες ερωτήσεις)';
            }
        }

        function startNextChapter() {
            document.getElementById('notes-input').value = '';
            document.getElementById('file-input').value = '';
            updateFileName();
            activeNotesText = '';

            // Επαναφέρουμε το input panel και κρύβουμε τα αποτελέσματα
            document.getElementById('results-area').style.display = 'none';
            document.getElementById('header-new-notes-btn').style.display = 'none';
            document.getElementById('input-panel').style.display = 'block';

            window.scrollTo({ top: 0, behavior: 'smooth' });
            document.getElementById('notes-input').focus();
        }
    </script>
</body>
</html>
    """