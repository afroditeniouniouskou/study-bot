import shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from rag_engine import ask_notes, RAGResponse
from ingest import run_ingestion

app = FastAPI(title="MSc AI Study & RAG Assistant")

DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)


class QuestionRequest(BaseModel):
    question: str
    top_k: int = 5


@app.post("/api/ask", response_model=RAGResponse)
def api_ask(payload: QuestionRequest):
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Η ερώτηση δεν μπορεί να είναι κενή.")
    try:
        return ask_notes(payload.question, top_k=payload.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in {".pdf", ".py"}:
        raise HTTPException(status_code=400, detail="Υποστηρίζονται μόνο αρχεία .pdf και .py")

    dest_path = DATA_DIR / file.filename
    with dest_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        run_ingestion()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Σφάλμα κατά την επεξεργασία: {e}")

    return {"message": f"Το αρχείο '{file.filename}' προστέθηκε επιτυχώς στη βάση γνώσης!"}


@app.get("/", response_class=HTMLResponse)
def serve_ui():
    return """
<!DOCTYPE html>
<html lang="el">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MSc AI Notes Assistant (RAG)</title>
    <style>
        :root {
            --bg: #0f172a;
            --card: #1e293b;
            --border: #334155;
            --text: #f8fafc;
            --muted: #94a3b8;
            --accent: #38bdf8;
            --accent-hover: #0284c7;
            --success: #22c55e;
            --warn: #f59e0b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, sans-serif; }
        body { background: var(--bg); color: var(--text); display: flex; flex-direction: column; height: 100vh; }
        header {
            padding: 16px 24px; background: var(--card); border-bottom: 1px solid var(--border);
            display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;
        }
        header h1 { font-size: 1.2rem; display: flex; align-items: center; gap: 8px; }
        .badge { font-size: 0.75rem; background: rgba(56, 189, 248, 0.15); color: var(--accent); padding: 3px 8px; border-radius: 999px; border: 1px solid rgba(56, 189, 248, 0.3); }
        .upload-box { display: flex; align-items: center; gap: 8px; }
        input[type="file"] { font-size: 0.85rem; color: var(--muted); }
        button {
            background: var(--accent); color: #0f172a; font-weight: 600; border: none;
            padding: 8px 14px; border-radius: 8px; cursor: pointer; transition: 0.2s;
        }
        button:hover { background: var(--accent-hover); color: white; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        #chat-container {
            flex: 1; overflow-y: auto; padding: 24px; max-width: 900px; width: 100%; margin: 0 auto;
            display: flex; flex-direction: column; gap: 18px;
        }
        .msg { padding: 16px; border-radius: 12px; line-height: 1.6; max-width: 88%; }
        .user-msg { background: #2563eb; align-self: flex-end; color: white; }
        .bot-msg { background: var(--card); border: 1px solid var(--border); align-self: flex-start; width: 100%; }
        .status-tag { display: inline-block; font-size: 0.75rem; padding: 2px 8px; border-radius: 6px; margin-bottom: 10px; font-weight: 600; }
        .found { background: rgba(34, 197, 94, 0.15); color: var(--success); }
        .not-found { background: rgba(245, 158, 11, 0.15); color: var(--warn); }
        .citations { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 8px; }
        .citations-title { font-size: 0.8rem; color: var(--muted); font-weight: 600; text-transform: uppercase; }
        .citation-card { background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border); padding: 10px 12px; border-radius: 8px; font-size: 0.85rem; }
        .citation-meta { color: var(--accent); font-weight: 600; margin-bottom: 4px; }
        .citation-snippet { color: var(--muted); font-style: italic; }
        footer {
            padding: 16px 24px; background: var(--card); border-top: 1px solid var(--border);
        }
        .input-bar { max-width: 900px; margin: 0 auto; display: flex; gap: 10px; }
        #question-input {
            flex: 1; padding: 12px 16px; border-radius: 10px; border: 1px solid var(--border);
            background: var(--bg); color: var(--text); font-size: 1rem; outline: none;
        }
        #question-input:focus { border-color: var(--accent); }
    </style>
</head>
<body>
    <header>
        <h1>🎓 MSc AI Notes Assistant <span class="badge">RAG + Citations</span></h1>
        <div class="upload-box">
            <input type="file" id="file-input" accept=".pdf,.py">
            <button id="upload-btn" onclick="uploadFile()">+ Προσθήκη Αρχείου</button>
        </div>
    </header>

    <div id="chat-container">
        <div class="msg bot-msg">
            Καλώς ήρθες! Ρώτησέ με οτιδήποτε πάνω στις σημειώσεις σου (PDF & Python). Θα σου απαντήσω αποκλειστικά με βάση το υλικό σου και θα σου δείξω τις ακριβείς σελίδες.
        </div>
    </div>

    <footer>
        <div class="input-bar">
            <input type="text" id="question-input" placeholder="Π.χ. Ποιες είναι οι βασικές δομές δεδομένων στη βιβλιοθήκη Pandas;" onkeypress="if(event.key==='Enter') sendQuestion()">
            <button id="send-btn" onclick="sendQuestion()">Αποστολή</button>
        </div>
    </footer>

    <script>
        const chat = document.getElementById('chat-container');

        function appendUserMessage(text) {
            const div = document.createElement('div');
            div.className = 'msg user-msg';
            div.textContent = text;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        function appendBotMessage(data) {
            const div = document.createElement('div');
            div.className = 'msg bot-msg';

            const statusHtml = data.found_in_notes
                ? `<span class="status-tag found">✓ Βρέθηκε στις σημειώσεις</span>`
                : `<span class="status-tag not-found">⚠ Δεν βρέθηκε ρητά στις σημειώσεις</span>`;

            let citationsHtml = '';
            if (data.citations && data.citations.length > 0) {
                const cards = data.citations.map(c => `
                    <div class="citation-card">
                        <div class="citation-meta">📄 ${c.source_file} — Σελίδα ${c.page_number}</div>
                        <div class="citation-snippet">"${c.snippet}"</div>
                    </div>
                `).join('');
                citationsHtml = `
                    <div class="citations">
                        <div class="citations-title">Πηγές & Παραπομπές</div>
                        ${cards}
                    </div>
                `;
            }

            div.innerHTML = `${statusHtml}<div style="white-space: pre-wrap;">${data.answer}</div>${citationsHtml}`;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        async function sendQuestion() {
            const input = document.getElementById('question-input');
            const btn = document.getElementById('send-btn');
            const question = input.value.trim();
            if (!question) return;

            appendUserMessage(question);
            input.value = '';
            btn.disabled = true;
            btn.textContent = 'Αναζήτηση...';

            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'msg bot-msg';
            loadingDiv.textContent = '⏳ Αναζήτηση στις σημειώσεις και σύνταξη απάντησης...';
            chat.appendChild(loadingDiv);

            try {
                const res = await fetch('/api/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question })
                });
                const data = await res.json();
                chat.removeChild(loadingDiv);
                if (!res.ok) throw new Error(data.detail || 'Σφάλμα διακομιστή');
                appendBotMessage(data);
            } catch (err) {
                chat.removeChild(loadingDiv);
                appendBotMessage({ answer: '❌ Σφάλμα: ' + err.message, found_in_notes: false, citations: [] });
            } finally {
                btn.disabled = false;
                btn.textContent = 'Αποστολή';
            }
        }

        async function uploadFile() {
            const fileInput = document.getElementById('file-input');
            const btn = document.getElementById('upload-btn');
            if (!fileInput.files.length) return alert('Επίλεξε πρώτα ένα αρχείο .pdf ή .py');

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);

            btn.disabled = true;
            btn.textContent = 'Επεξεργασία...';

            try {
                const res = await fetch('/api/upload', { method: 'POST', body: formData });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail);
                alert('✅ ' + data.message);
                fileInput.value = '';
            } catch (err) {
                alert('❌ Σφάλμα: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.textContent = '+ Προσθήκη Αρχείου';
            }
        }
    </script>
</body>
</html>
    """