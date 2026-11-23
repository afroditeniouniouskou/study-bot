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
        result = generate_study_guide_and_quiz(combined_text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/extract-text")
async def api_extract_text(
    notes_text: str = Form(""),
    file: Optional[UploadFile] = File(None),
):
    combined_text = notes_text.strip()
    if file and file.filename:
        file_bytes = await file.read()
        if file_bytes:
            extracted = extract_text_from_bytes(file_bytes, file.filename)
            combined_text = f"{combined_text}\n\n{extracted}".strip() if combined_text else extracted
    return {"text": combined_text}


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

        /* Κάρτα επόμενων βημάτων μετά την υποβολή */
        .next-steps-box {
            margin-top: 22px; padding: 20px; border-radius: 12px;
            background: rgba(15, 23, 42, 0.85); border: 1px solid var(--accent);
            display: none; flex-direction: column; gap: 14px;
        }
        .next-steps-msg { font-size: 1.02rem; line-height: 1.5; color: #f8fafc; }
        .next-steps-actions { display: flex; flex-wrap: wrap; gap: 10px; }
        .action-btn {
            padding: 10px 16px; border-radius: 8px; font-weight: 600; font-size: 0.9rem;
            cursor: pointer; border: 1px solid var(--border); transition: 0.2s;
        }
        .btn-retry { background: rgba(245, 158, 11, 0.18); color: #fcd34d; border-color: rgba(245, 158, 11, 0.4); }
        .btn-retry:hover { background: rgba(245, 158, 11, 0.3); }
        .btn-new-quiz { background: rgba(56, 189, 248, 0.18); color: #7dd3fc; border-color: rgba(56, 189, 248, 0.4); }
        .btn-new-quiz:hover { background: rgba(56, 189, 248, 0.3); }
        .btn-new-quiz:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-next-chapter { background: var(--accent); color: #0f172a; border: none; }
        .btn-next-chapter:hover { background: var(--accent-hover); color: white; }
    </style>
</head>
<body>
    <header>
        <h1>🧠 AI Study Explainer & Quiz <span class="badge">Instant Comprehension</span></h1>
    </header>

    <div class="container">
        <div class="panel" id="input-panel">
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

                <div class="next-steps-box" id="next-steps-box">
                    <div class="next-steps-msg" id="next-steps-msg"></div>
                    <div class="next-steps-actions">
                        <button class="action-btn btn-retry" id="retry-btn" onclick="retryCurrentQuiz()">🔄 Επανάληψη ίδιου Quiz</button>
                        <button class="action-btn btn-new-quiz" id="new-quiz-btn" onclick="requestNewQuiz()">🎲 Νέο Quiz (νέες ερωτήσεις)</button>
                        <button class="action-btn btn-next-chapter" onclick="startNextChapter()">📚 Επόμενο Κεφάλαιο (νέες σημειώσεις)</button>
                    </div>
                </div>
            </div>
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
            label.textContent = input.files.length ? input.files[0].name : 'Προαιρετικά: Ανέβασε .pdf, .txt ή .py';
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
                // Κρατάμε το κείμενο των σημειώσεων για μελλοντικά νέα quizzes
                const textRes = await fetch('/api/extract-text', { method: 'POST', body: formData });
                if (textRes.ok) {
                    const textData = await textRes.json();
                    activeNotesText = textData.text;
                } else {
                    activeNotesText = notes;
                }

                const res = await fetch('/api/study', { method: 'POST', body: formData });
                const rawText = await res.text();
                let data;
                try { data = JSON.parse(rawText); }
                catch { throw new Error(`Σφάλμα διακομιστή (HTTP ${res.status}).`); }

                if (!res.ok) throw new Error(data.detail || 'Αποτυχία επεξήγησης');
                renderResults(data);
            } catch (err) {
                alert('❌ ' + err.message);
            } finally {
                btn.disabled = false;
                btn.textContent = '✨ Εξήγηση & Δημιουργία Quiz';
            }
        }

        function renderResults(data) {
            document.getElementById('results-area').style.display = 'flex';
            document.getElementById('result-title').textContent = '📖 ' + data.title;
            document.getElementById('explanation-box').textContent = data.simple_explanation;

            const list = document.getElementById('takeaways-list');
            list.innerHTML = data.key_takeaways.map(item => `<li>${item}</li>`).join('');

            renderQuizQuestions(data.quiz);
            document.getElementById('results-area').scrollIntoView({ behavior: 'smooth' });
        }

        function renderQuizQuestions(quizList) {
            currentQuizData = quizList;
            userSelections = {};
            isSubmitted = false;

            document.getElementById('next-steps-box').style.display = 'none';

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
                qTitle.textContent = `${qIdx + 1}. ${q.question}`;
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

            document.getElementById('score-display').textContent = `Τελικό Σκορ: ${score} / ${total}`;

            const submitBtn = document.getElementById('submit-quiz-btn');
            submitBtn.style.display = 'none';

            // Εμφάνιση της κάρτας με τις επιλογές συνέχειας
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
            document.getElementById('results-area').style.display = 'none';
            document.getElementById('input-panel').scrollIntoView({ behavior: 'smooth' });
            document.getElementById('notes-input').focus();
        }
    </script>
</body>
</html>
    """