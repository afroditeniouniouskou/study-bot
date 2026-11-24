from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from rag_engine import (
    extract_text_from_bytes,
    generate_study_guide_and_quiz,
    generate_new_quiz,
    answer_voice_question,
    StudyGuideResponse,
    NewQuizResponse,
    VoiceAnswerResponse,
)

app = FastAPI(title="Study Studio — Explainer, Voice Tutor & Quiz")


class NewQuizRequest(BaseModel):
    notes_text: str
    previous_questions: list[str] = []


class VoiceQuestionRequest(BaseModel):
    notes_text: str
    question: str


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


@app.post("/api/voice-ask", response_model=VoiceAnswerResponse)
def api_voice_ask(payload: VoiceQuestionRequest):
    if len(payload.notes_text.strip()) < 20:
        raise HTTPException(status_code=400, detail="Δεν βρέθηκαν σημειώσεις μαθήματος.")
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Δεν ακούστηκε ερώτηση.")
    try:
        return answer_voice_question(payload.notes_text, payload.question)
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
    <title>Study Studio</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-gradient: linear-gradient(160deg, #F8D675 0%, #F98A8B 100%);
            --ink: #0b192c;
            --ink-secondary: #1e3a5f;
            --ink-muted: #486581;

            --btn-blue: #0f294a;
            --btn-blue-hover: #1d4ed8;

            --surface: rgba(255, 255, 255, 0.92);
            --surface-warm: rgba(255, 252, 244, 0.95);
            --line: rgba(11, 25, 44, 0.1);

            --success: #059669;
            --danger: #e11d48;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            -webkit-font-smoothing: antialiased;
        }

        body {
            background: var(--bg-gradient);
            background-attachment: fixed;
            color: var(--ink);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        header {
            padding: 20px 32px;
            background: rgba(255, 255, 255, 0.45);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-bottom: 1px solid rgba(11, 25, 44, 0.08);
            display: flex;
            justify-content: center;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 30;
        }

        .brand {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
        }

        .brand h1 {
            font-size: 1.75rem;
            font-weight: 800;
            color: var(--btn-blue);
            letter-spacing: -0.035em;
        }

        .brand span {
            font-size: 0.78rem;
            font-weight: 600;
            color: var(--ink-secondary);
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        .header-actions {
            display: none;
            position: absolute;
            right: 32px;
            gap: 10px;
            align-items: center;
        }

        .header-reset-btn {
            background: var(--btn-blue);
            color: #ffffff;
            border: none;
            padding: 9px 16px;
            border-radius: 8px;
            font-size: 0.84rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .header-reset-btn:hover { background: var(--btn-blue-hover); transform: translateY(-1px); }

        .header-mode-btn {
            background: #ffffff;
            color: var(--btn-blue);
            border: 1px solid rgba(15, 41, 74, 0.25);
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 0.84rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .header-mode-btn:hover { background: rgba(15, 41, 74, 0.06); }

        @media (max-width: 780px) {
            header { flex-direction: column; gap: 12px; padding: 16px 20px; }
            .header-actions { position: static; flex-wrap: wrap; justify-content: center; }
        }

        .workspace {
            flex: 1;
            width: 100%;
            max-width: 820px;
            margin: 0 auto;
            padding: 32px 20px 80px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .workspace.active-study {
            justify-content: flex-start;
            padding-top: 36px;
        }

        .composer-card {
            width: 100%;
            background: var(--surface);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.95);
            border-radius: 16px;
            padding: 32px;
            box-shadow: 0 24px 48px -12px rgba(11, 25, 44, 0.18);
        }

        .composer-top {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 16px;
            gap: 12px;
            flex-wrap: wrap;
        }

        .composer-top h2 {
            font-size: 1.15rem;
            font-weight: 700;
            color: var(--ink);
            letter-spacing: -0.015em;
        }

        .sample-btn {
            font-size: 0.84rem;
            font-weight: 600;
            color: var(--btn-blue);
            background: transparent;
            border: none;
            cursor: pointer;
            padding: 4px 0;
            border-bottom: 1px solid rgba(15, 41, 74, 0.3);
            transition: 0.15s;
        }
        .sample-btn:hover { color: var(--btn-blue-hover); border-color: var(--btn-blue-hover); }

        textarea {
            width: 100%;
            min-height: 180px;
            padding: 16px 18px;
            border-radius: 10px;
            border: 1px solid rgba(11, 25, 44, 0.15);
            background: #ffffff;
            color: var(--ink);
            font-size: 0.98rem;
            line-height: 1.65;
            resize: vertical;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        textarea::placeholder { color: #829ab1; }
        textarea:focus {
            border-color: var(--btn-blue);
            box-shadow: 0 0 0 3px rgba(15, 41, 74, 0.1);
        }

        .composer-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 14px;
            margin-top: 20px;
            padding-top: 18px;
            border-top: 1px solid var(--line);
        }

        .upload-trigger {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 10px 16px;
            background: rgba(11, 25, 44, 0.04);
            border: 1px solid rgba(11, 25, 44, 0.14);
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.88rem;
            font-weight: 600;
            color: var(--ink-secondary);
            transition: all 0.15s ease;
        }
        .upload-trigger:hover {
            background: rgba(11, 25, 44, 0.08);
            color: var(--ink);
            border-color: rgba(11, 25, 44, 0.28);
        }

        .mode-choice-group {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .btn-primary {
            background: var(--btn-blue);
            color: #ffffff;
            font-weight: 700;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.92rem;
            letter-spacing: -0.01em;
            box-shadow: 0 4px 12px rgba(15, 41, 74, 0.22);
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .btn-primary:hover { background: var(--btn-blue-hover); transform: translateY(-1px); }
        .btn-primary:disabled { opacity: 0.55; cursor: not-allowed; transform: none; }

        .btn-secondary {
            background: #ffffff;
            color: var(--btn-blue);
            font-weight: 700;
            border: 1.5px solid var(--btn-blue);
            padding: 11px 18px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.92rem;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .btn-secondary:hover { background: rgba(15, 41, 74, 0.06); transform: translateY(-1px); }
        .btn-secondary:disabled { opacity: 0.55; cursor: not-allowed; transform: none; }

        /* VOICE TUTOR PANEL */
        .voice-panel {
            display: none;
            flex-direction: column;
            gap: 22px;
            background: var(--surface-warm);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.95);
            border-radius: 16px;
            padding: 36px;
            box-shadow: 0 24px 48px -12px rgba(11, 25, 44, 0.16);
        }

        .voice-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 14px;
            flex-wrap: wrap;
            padding-bottom: 18px;
            border-bottom: 1px solid var(--line);
        }

        .voice-status-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 700;
            background: rgba(15, 41, 74, 0.08);
            color: var(--btn-blue);
        }
        .voice-status-badge.speaking {
            background: rgba(5, 150, 105, 0.14);
            color: #065f46;
        }
        .voice-status-badge.listening {
            background: rgba(225, 29, 72, 0.14);
            color: #9f1239;
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: currentColor;
            animation: pulse 1.2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(1.3); }
        }

        .voice-card-live {
            background: #ffffff;
            border: 1px solid rgba(11, 25, 44, 0.1);
            border-radius: 12px;
            padding: 22px 24px;
        }

        .voice-sec-label {
            font-size: 0.78rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--ink-muted);
            margin-bottom: 6px;
        }

        .voice-sec-title {
            font-size: 1.22rem;
            font-weight: 800;
            color: var(--btn-blue);
            margin-bottom: 12px;
        }

        .voice-transcript {
            font-size: 1.02rem;
            line-height: 1.75;
            color: var(--ink);
            white-space: pre-wrap;
        }

        .voice-controls {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
        }

        .btn-mic {
            background: #e11d48;
            color: #ffffff;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 0.92rem;
            font-weight: 700;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 4px 12px rgba(225, 29, 72, 0.25);
            transition: 0.2s;
        }
        .btn-mic:hover { background: #be123c; }
        .btn-mic.recording { background: #9f1239; animation: pulse 1s infinite; }

        .voice-qa-box {
            margin-top: 6px;
            padding-top: 18px;
            border-top: 1px solid var(--line);
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .voice-ask-row {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .voice-ask-input {
            flex: 1;
            min-width: 220px;
            padding: 11px 14px;
            border-radius: 8px;
            border: 1px solid rgba(11, 25, 44, 0.18);
            font-size: 0.94rem;
            outline: none;
        }
        .voice-ask-input:focus { border-color: var(--btn-blue); }

        .qa-bubble {
            padding: 14px 16px;
            border-radius: 10px;
            background: rgba(248, 214, 117, 0.25);
            border: 1px solid rgba(11, 25, 44, 0.08);
            font-size: 0.95rem;
            line-height: 1.65;
            display: none;
        }

        /* READING & QUIZ RESULTS */
        .results-stack {
            display: none;
            flex-direction: column;
            gap: 32px;
            width: 100%;
        }

        .summary-sheet {
            background: var(--surface-warm);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.95);
            border-radius: 16px;
            padding: 36px;
            box-shadow: 0 20px 40px -15px rgba(11, 25, 44, 0.14);
        }

        .summary-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 16px;
            flex-wrap: wrap;
            padding-bottom: 18px;
            border-bottom: 1px solid var(--line);
            margin-bottom: 24px;
        }

        .eyebrow {
            font-size: 0.74rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--ink-muted);
            margin-bottom: 6px;
            display: block;
        }

        .doc-title {
            font-size: 1.55rem;
            font-weight: 800;
            color: var(--ink);
            letter-spacing: -0.025em;
            line-height: 1.25;
        }

        .page-indicator {
            font-size: 0.82rem;
            font-weight: 700;
            color: var(--btn-blue);
            background: rgba(248, 214, 117, 0.35);
            padding: 6px 14px;
            border-radius: 999px;
            white-space: nowrap;
        }

        .section-heading {
            font-size: 1.18rem;
            font-weight: 800;
            color: var(--btn-blue);
            margin-bottom: 14px;
            letter-spacing: -0.015em;
        }

        .doc-body {
            font-size: 1.02rem;
            line-height: 1.85;
            color: var(--ink);
            white-space: pre-wrap;
            font-weight: 400;
        }

        .example-callout {
            margin-top: 22px;
            padding: 18px 20px;
            border-radius: 12px;
            background: rgba(248, 214, 117, 0.24);
            border: 1px solid rgba(11, 25, 44, 0.08);
        }

        .example-label {
            display: inline-block;
            font-size: 0.75rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--btn-blue);
            margin-bottom: 8px;
        }

        .example-text {
            font-size: 0.96rem;
            line-height: 1.7;
            color: var(--ink);
            white-space: pre-wrap;
            font-weight: 500;
        }

        .key-points-section {
            margin-top: 24px;
            padding-top: 20px;
            border-top: 1px solid var(--line);
        }

        .key-points-section h3 {
            font-size: 0.8rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--btn-blue);
            margin-bottom: 12px;
        }

        .key-points-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .key-point-row {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 10px 14px;
            background: rgba(11, 25, 44, 0.04);
            border-radius: 8px;
            font-size: 0.93rem;
            line-height: 1.55;
            color: var(--ink);
            font-weight: 500;
        }

        .kp-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--btn-blue);
            margin-top: 8px;
            flex-shrink: 0;
        }

        .pagination-bar {
            margin-top: 28px;
            padding-top: 20px;
            border-top: 1px solid var(--line);
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
        }

        .page-dots {
            display: flex;
            gap: 7px;
            align-items: center;
        }

        .page-dot {
            width: 9px;
            height: 9px;
            border-radius: 999px;
            background: rgba(15, 41, 74, 0.2);
            border: none;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .page-dot.active {
            width: 24px;
            background: var(--btn-blue);
        }

        .nav-page-btn {
            padding: 9px 18px;
            border-radius: 8px;
            font-size: 0.88rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.15s ease;
            border: 1px solid rgba(15, 41, 74, 0.22);
            background: #ffffff;
            color: var(--btn-blue);
        }
        .nav-page-btn:hover:not(:disabled) {
            background: var(--btn-blue);
            color: #ffffff;
            border-color: var(--btn-blue);
        }
        .nav-page-btn:disabled {
            opacity: 0.35;
            cursor: not-allowed;
        }

        .quiz-module {
            background: var(--surface);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.95);
            border-radius: 16px;
            padding: 36px;
            box-shadow: 0 20px 40px -15px rgba(11, 25, 44, 0.14);
        }

        .quiz-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            flex-wrap: wrap;
            gap: 12px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--line);
            margin-bottom: 24px;
        }

        .quiz-top h2 {
            font-size: 1.35rem;
            font-weight: 800;
            color: var(--ink);
            letter-spacing: -0.02em;
        }

        .status-chip {
            font-size: 0.84rem;
            font-weight: 700;
            padding: 6px 14px;
            border-radius: 999px;
            background: rgba(11, 25, 44, 0.06);
            color: var(--ink-secondary);
        }
        .status-chip.done {
            background: var(--btn-blue);
            color: #ffffff;
        }

        .question-block {
            padding: 22px 0;
            border-bottom: 1px solid var(--line);
        }
        .question-block:first-child { padding-top: 0; }
        .question-block:last-child { border-bottom: none; padding-bottom: 0; }

        .q-header {
            display: flex;
            gap: 12px;
            align-items: baseline;
            margin-bottom: 14px;
        }

        .q-index {
            font-size: 0.82rem;
            font-weight: 800;
            color: var(--btn-blue);
            background: rgba(249, 138, 139, 0.35);
            padding: 3px 9px;
            border-radius: 6px;
        }

        .q-text {
            font-size: 1.03rem;
            font-weight: 700;
            color: var(--ink);
            line-height: 1.5;
        }

        .choices-grid {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .choice-btn {
            display: flex;
            align-items: center;
            gap: 12px;
            width: 100%;
            text-align: left;
            padding: 12px 16px;
            border-radius: 10px;
            border: 1px solid rgba(11, 25, 44, 0.14);
            background: #ffffff;
            color: var(--ink);
            font-size: 0.95rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
        }

        .choice-letter {
            width: 24px;
            height: 24px;
            border-radius: 6px;
            background: rgba(11, 25, 44, 0.06);
            color: var(--ink-secondary);
            font-size: 0.78rem;
            font-weight: 700;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }

        .choice-btn:hover:not(:disabled) {
            border-color: var(--btn-blue);
            background: rgba(248, 214, 117, 0.18);
        }

        .choice-btn.selected {
            border-color: var(--btn-blue);
            background: rgba(15, 41, 74, 0.06);
            font-weight: 700;
        }
        .choice-btn.selected .choice-letter {
            background: var(--btn-blue);
            color: #ffffff;
        }

        .choice-btn.correct {
            border-color: var(--success);
            background: rgba(5, 150, 105, 0.1);
            color: #064e3b;
            font-weight: 700;
        }
        .choice-btn.correct .choice-letter {
            background: var(--success);
            color: #ffffff;
        }

        .choice-btn.wrong {
            border-color: var(--danger);
            background: rgba(225, 29, 72, 0.08);
            color: #881337;
        }
        .choice-btn.wrong .choice-letter {
            background: var(--danger);
            color: #ffffff;
        }

        .q-rationale {
            margin-top: 12px;
            padding: 12px 16px;
            border-radius: 8px;
            background: rgba(11, 25, 44, 0.04);
            font-size: 0.9rem;
            line-height: 1.55;
            color: var(--ink-secondary);
            display: none;
        }

        .btn-submit-full {
            width: 100%;
            margin-top: 28px;
            padding: 14px 24px;
            background: var(--btn-blue);
            color: #ffffff;
            border: none;
            border-radius: 10px;
            font-size: 0.98rem;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 6px 18px rgba(15, 41, 74, 0.22);
            transition: all 0.2s ease;
        }
        .btn-submit-full:hover { background: var(--btn-blue-hover); transform: translateY(-1px); }

        .completion-bar {
            margin-top: 28px;
            padding: 24px;
            border-radius: 12px;
            background: rgba(248, 214, 117, 0.24);
            border: 1px solid rgba(11, 25, 44, 0.12);
            display: none;
            flex-direction: column;
            gap: 16px;
        }
        .completion-text {
            font-size: 1rem;
            line-height: 1.6;
            color: var(--ink);
            font-weight: 500;
        }
        .completion-actions {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .btn-outline {
            padding: 10px 18px;
            border-radius: 8px;
            background: #ffffff;
            color: var(--btn-blue);
            border: 1px solid rgba(15, 41, 74, 0.25);
            font-size: 0.9rem;
            font-weight: 700;
            cursor: pointer;
            transition: 0.15s;
        }
        .btn-outline:hover { border-color: var(--btn-blue); background: rgba(15, 41, 74, 0.04); }
        .btn-outline:disabled { opacity: 0.5; cursor: not-allowed; }
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <h1>Study Studio</h1>
            <span>Voice Tutor &amp; Comprehension</span>
        </div>
        <div class="header-actions" id="header-actions">
            <button class="header-mode-btn" id="switch-mode-btn" onclick="toggleStudyMode()">Αλλαγή Τρόπου Μελέτης</button>
            <button class="header-reset-btn" onclick="startNextChapter()">Νέες Σημειώσεις</button>
        </div>
    </header>

    <main class="workspace" id="main-wrapper">
        <section class="composer-card" id="input-panel">
            <div class="composer-top">
                <h2>Εισαγωγή Σημειώσεων</h2>
                <button type="button" class="sample-btn" onclick="fillDemoNotes()">Δοκιμή με παράδειγμα</button>
            </div>
            <textarea id="notes-input" placeholder="Επικόλλησε το κείμενο των σημειώσεών σου ή επίλεξε ένα αρχείο..."></textarea>

            <div class="composer-footer">
                <label class="upload-trigger">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
                    <span id="file-name">Επιλογή αρχείου (.pdf, .txt, .py)</span>
                    <input type="file" id="file-input" accept=".pdf,.txt,.py,.md" style="display:none" onchange="updateFileName()">
                </label>

                <div class="mode-choice-group">
                    <button class="btn-secondary" id="btn-read-mode" onclick="startStudy('read')">
                        📖 Διάβασμα Περίληψης
                    </button>
                    <button class="btn-primary" id="btn-voice-mode" onclick="startStudy('voice')">
                        🎙️ Φωνητική Εξήγηση
                    </button>
                </div>
            </div>
        </section>

        <!-- VOICE TUTOR VIEW -->
        <section class="voice-panel" id="voice-area">
            <div class="voice-top">
                <div>
                    <span class="eyebrow">Φωνητικός Καθηγητής · Απλοϊκή Ανάλυση</span>
                    <h2 class="doc-title" id="voice-title">Τίτλος Μαθήματος</h2>
                </div>
                <span class="voice-status-badge" id="voice-status">
                    <span class="pulse-dot"></span>
                    <span id="voice-status-text">Έτοιμο</span>
                </span>
            </div>

            <div class="voice-card-live">
                <div class="voice-sec-label" id="voice-sec-counter">Ενότητα 1 από 1</div>
                <div class="voice-sec-title" id="voice-sec-title">Τίτλος Ενότητας</div>
                <div class="voice-transcript" id="voice-transcript"></div>
            </div>

            <div class="voice-controls">
                <button class="btn-secondary" id="voice-prev-btn" onclick="voiceChangeSection(-1)">← Προηγούμενη</button>
                <button class="btn-primary" id="voice-play-pause-btn" onclick="toggleVoicePlayPause()">⏸ Παύση</button>
                <button class="btn-secondary" id="voice-next-btn" onclick="voiceChangeSection(1)">Επόμενη Ενότητα →</button>
                <button class="btn-mic" id="mic-btn" onclick="startVoiceQuestion()">🎤 Κάνε Φωνητική Ερώτηση</button>
            </div>

            <div class="voice-qa-box">
                <div class="eyebrow">Έχεις απορία; Διέκοψέ με με φωνή ή γράψε την ερώτησή σου:</div>
                <div class="voice-ask-row">
                    <input type="text" class="voice-ask-input" id="voice-text-question" placeholder="Π.χ. Μπορείς να μου το εξηγήσεις με ένα ακόμα πιο απλό παράδειγμα;" onkeydown="if(event.key==='Enter') submitVoiceQuestion()">
                    <button class="btn-primary" id="voice-send-q-btn" onclick="submitVoiceQuestion()">Ερώτηση</button>
                </div>
                <div class="qa-bubble" id="voice-qa-bubble"></div>
            </div>
        </section>

        <!-- READING & QUIZ VIEW -->
        <div class="results-stack" id="results-area">
            <article class="summary-sheet" id="summary-sheet">
                <div class="summary-header">
                    <div>
                        <span class="eyebrow">01 · Απλοϊκός Οδηγός Μελέτης</span>
                        <h2 class="doc-title" id="result-title">Τίτλος Ενότητας</h2>
                    </div>
                    <span class="page-indicator" id="page-indicator">Σελίδα 1 από 1</span>
                </div>

                <div id="summary-page-content">
                    <h3 class="section-heading" id="sec-heading"></h3>
                    <div class="doc-body" id="sec-explanation"></div>

                    <div class="example-callout" id="sec-example-box">
                        <span class="example-label">Καθημερινό Παράδειγμα</span>
                        <div class="example-text" id="sec-example"></div>
                    </div>
                </div>

                <div class="key-points-section" id="takeaways-wrapper" style="display:none;">
                    <h3>Σημεία-Κλειδιά Ενότητας</h3>
                    <div class="key-points-list" id="takeaways-list"></div>
                </div>

                <div class="pagination-bar">
                    <button type="button" class="nav-page-btn" id="prev-page-btn" onclick="changeSummaryPage(-1)">← Προηγούμενη</button>
                    <div class="page-dots" id="page-dots"></div>
                    <button type="button" class="nav-page-btn" id="next-page-btn" onclick="changeSummaryPage(1)">Επόμενη →</button>
                </div>
            </article>

            <section class="quiz-module">
                <div class="quiz-top">
                    <div>
                        <span class="eyebrow">02 · Αυτοαξιολόγηση</span>
                        <h2>Έλεγχος Κατανόησης</h2>
                    </div>
                    <span class="status-chip" id="score-display">0 / 0 επιλεγμένα</span>
                </div>

                <div id="quiz-container"></div>
                <button class="btn-submit-full" id="submit-quiz-btn" onclick="submitQuiz()">Υποβολή Απαντήσεων</button>

                <div class="completion-bar" id="next-steps-box">
                    <div class="completion-text" id="next-steps-msg"></div>
                    <div class="completion-actions">
                        <button class="btn-outline" id="retry-btn" onclick="retryCurrentQuiz()">Επανάληψη Quiz</button>
                        <button class="btn-outline" id="new-quiz-btn" onclick="requestNewQuiz()">Νέες Ερωτήσεις</button>
                        <button class="btn-primary" onclick="startNextChapter()">Επόμενο Κεφάλαιο</button>
                    </div>
                </div>
            </section>
        </div>
    </main>

    <script>
        let currentStudyData = null;
        let currentMode = 'read';
        let summarySections = [];
        let currentSummaryPage = 0;

        let voiceSectionIndex = 0;
        let isSpeaking = false;
        let isPaused = false;
        let recognition = null;

        let currentQuizData = [];
        let userSelections = {};
        let isSubmitted = false;
        let activeNotesText = "";
        const LETTERS = ["A", "B", "C", "D"];

        function updateFileName() {
            const input = document.getElementById('file-input');
            const label = document.getElementById('file-name');
            label.textContent = input.files.length ? input.files[0].name : 'Επιλογή αρχείου (.pdf, .txt, .py)';
        }

        function fillDemoNotes() {
            document.getElementById('notes-input').value =
`Το Gradient Descent (Κατάβαση Κλίσης) είναι ο βασικός αλγόριθμος βελτιστοποίησης στη Μηχανική Μάθηση. Σκοπός του είναι να ελαχιστοποιήσει τη συνάρτηση κόστους (Loss Function), η οποία μετρά πόσο απέχουν οι προβλέψεις του μοντέλου από τις πραγματικές τιμές. Σε κάθε βήμα, υπολογίζει την παράγωγο (gradient) της συνάρτησης κόστους ως προς τα βάρη (weights) και ενημερώνει τα βάρη προς την αντίθετη κατεύθυνση της κλίσης. Το μέγεθος του βήματος καθορίζεται από το Learning Rate (ρυθμός μάθησης): αν είναι πολύ μεγάλο, ο αλγόριθμος μπορεί να αστοχήσει και να αποκλίνει· αν είναι πολύ μικρό, η εκπαίδευση γίνεται εξαιρετικά αργή.`;
        }

        async function startStudy(mode) {
            const notes = document.getElementById('notes-input').value.trim();
            const fileInput = document.getElementById('file-input');
            const btnRead = document.getElementById('btn-read-mode');
            const btnVoice = document.getElementById('btn-voice-mode');

            if (!notes && !fileInput.files.length) {
                return alert('Πρόσθεσε σημειώσεις ή επίλεξε ένα αρχείο πρώτα.');
            }

            btnRead.disabled = true;
            btnVoice.disabled = true;
            if (mode === 'voice') {
                btnVoice.textContent = 'Προετοιμασία μαθήματος...';
            } else {
                btnRead.textContent = 'Επεξεργασία...';
            }

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

                currentStudyData = data;
                activeNotesText = data.extracted_text || notes;
                summarySections = data.sections || [];

                document.getElementById('input-panel').style.display = 'none';
                document.getElementById('main-wrapper').classList.add('active-study');
                document.getElementById('header-actions').style.display = 'flex';

                prepareReadingView(data);

                if (mode === 'voice') {
                    activateVoiceMode();
                } else {
                    activateReadMode();
                }
            } catch (err) {
                alert(err.message);
            } finally {
                btnRead.disabled = false;
                btnVoice.disabled = false;
                btnRead.textContent = '📖 Διάβασμα Περίληψης';
                btnVoice.textContent = '🎙️ Φωνητική Εξήγηση';
            }
        }

        function activateReadMode() {
            stopSpeech();
            currentMode = 'read';
            document.getElementById('voice-area').style.display = 'none';
            document.getElementById('results-area').style.display = 'flex';
            document.getElementById('switch-mode-btn').textContent = '🎙️ Άκουσε Φωνητικά';
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        function activateVoiceMode() {
            currentMode = 'voice';
            document.getElementById('results-area').style.display = 'none';
            document.getElementById('voice-area').style.display = 'flex';
            document.getElementById('switch-mode-btn').textContent = '📖 Διάβασμα & Quiz';
            document.getElementById('voice-title').textContent = currentStudyData.title;
            document.getElementById('voice-qa-bubble').style.display = 'none';
            voiceSectionIndex = 0;
            playVoiceSection(0);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        function toggleStudyMode() {
            if (currentMode === 'voice') {
                activateReadMode();
            } else {
                activateVoiceMode();
            }
        }

        /* --- VOICE TUTOR ENGINE --- */
        function setVoiceStatus(state, label) {
            const badge = document.getElementById('voice-status');
            badge.className = 'voice-status-badge ' + (state || '');
            document.getElementById('voice-status-text').textContent = label;
        }

        function stopSpeech() {
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
            }
            isSpeaking = false;
            isPaused = false;
            document.getElementById('voice-play-pause-btn').textContent = '▶ Επανάληψη';
            setVoiceStatus('', 'Σε αναμονή');
        }

        function speakGreekText(textToSpeak, onEndCallback) {
            if (!('speechSynthesis' in window)) {
                setVoiceStatus('', 'Ο browser δεν υποστηρίζει φωνή');
                return;
            }
            window.speechSynthesis.cancel();

            const utterance = new SpeechSynthesisUtterance(textToSpeak);
            utterance.lang = 'el-GR';
            utterance.rate = 0.98;
            utterance.pitch = 1.02;

            const voices = window.speechSynthesis.getVoices();
            const greekVoice = voices.find(v => v.lang && v.lang.toLowerCase().includes('el'));
            if (greekVoice) utterance.voice = greekVoice;

            utterance.onstart = () => {
                isSpeaking = true;
                isPaused = false;
                document.getElementById('voice-play-pause-btn').textContent = '⏸ Παύση';
                setVoiceStatus('speaking', 'Εξηγεί τώρα...');
            };

            utterance.onend = () => {
                isSpeaking = false;
                isPaused = false;
                document.getElementById('voice-play-pause-btn').textContent = '▶ Επανάληψη';
                setVoiceStatus('', 'Ολοκληρώθηκε');
                if (onEndCallback) onEndCallback();
            };

            utterance.onerror = () => {
                isSpeaking = false;
                isPaused = false;
                setVoiceStatus('', 'Έτοιμο');
            };

            window.speechSynthesis.speak(utterance);
        }

        function playVoiceSection(idx) {
            if (!summarySections.length) return;
            voiceSectionIndex = idx;
            const total = summarySections.length;
            const sec = summarySections[idx];

            document.getElementById('voice-sec-counter').textContent = `Ενότητα ${idx + 1} από ${total}`;
            document.getElementById('voice-sec-title').textContent = sec.heading;

            const fullText = `${sec.explanation}\n\nΓια παράδειγμα: ${sec.example}`;
            document.getElementById('voice-transcript').textContent = fullText;

            document.getElementById('voice-prev-btn').disabled = (idx === 0);
            document.getElementById('voice-next-btn').disabled = (idx === total - 1);

            const intro = idx === 0
                ? `Πάμε να δούμε το μάθημα ${currentStudyData.title}. Πρώτο μέρος: ${sec.heading}. `
                : `Ενότητα ${idx + 1}: ${sec.heading}. `;

            speakGreekText(`${intro}${sec.explanation}. Για να το καταλάβεις ακόμα πιο απλά, δες ένα παράδειγμα: ${sec.example}`);
        }

        function voiceChangeSection(delta) {
            const next = voiceSectionIndex + delta;
            if (next >= 0 && next < summarySections.length) {
                playVoiceSection(next);
            }
        }

        function toggleVoicePlayPause() {
            if (!('speechSynthesis' in window)) return;
            const btn = document.getElementById('voice-play-pause-btn');

            if (isSpeaking && !isPaused) {
                window.speechSynthesis.pause();
                isPaused = true;
                btn.textContent = '▶ Συνέχεια';
                setVoiceStatus('', 'Σε παύση');
            } else if (isPaused) {
                window.speechSynthesis.resume();
                isPaused = false;
                btn.textContent = '⏸ Παύση';
                setVoiceStatus('speaking', 'Εξηγεί τώρα...');
            } else {
                playVoiceSection(voiceSectionIndex);
            }
        }

        function startVoiceQuestion() {
            stopSpeech();
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                alert('Ο browser σου δεν υποστηρίζει φωνητική αναγνώριση. Μπορείς να γράψεις την ερώτησή σου στο πεδίο από κάτω.');
                document.getElementById('voice-text-question').focus();
                return;
            }

            if (recognition) {
                try { recognition.stop(); } catch {}
            }

            recognition = new SpeechRecognition();
            recognition.lang = 'el-GR';
            recognition.interimResults = false;
            recognition.maxAlternatives = 1;

            const micBtn = document.getElementById('mic-btn');
            micBtn.classList.add('recording');
            micBtn.textContent = '🔴 Μίλα τώρα...';
            setVoiceStatus('listening', 'Σε ακούω...');

            recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                document.getElementById('voice-text-question').value = transcript;
                submitVoiceQuestion();
            };

            recognition.onerror = (event) => {
                setVoiceStatus('', 'Δεν ακούστηκε ερώτηση');
                if (event.error === 'not-allowed') {
                    alert('Δώσε άδεια στο μικρόφωνο από τον browser για να ρωτήσεις φωνητικά.');
                }
            };

            recognition.onend = () => {
                micBtn.classList.remove('recording');
                micBtn.textContent = '🎤 Κάνε Φωνητική Ερώτηση';
            };

            recognition.start();
        }

        async function submitVoiceQuestion() {
            const input = document.getElementById('voice-text-question');
            const question = input.value.trim();
            if (!question) return;

            stopSpeech();
            const btn = document.getElementById('voice-send-q-btn');
            const bubble = document.getElementById('voice-qa-bubble');

            btn.disabled = true;
            btn.textContent = 'Σκέφτομαι...';
            setVoiceStatus('', 'Ετοιμάζω απάντηση...');

            try {
                const res = await fetch('/api/voice-ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        notes_text: activeNotesText,
                        question: question,
                    }),
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Αποτυχία απάντησης');

                bubble.style.display = 'block';
                bubble.innerHTML = `<strong>Ερώτηση:</strong> ${question}<br><br><strong>Απάντηση:</strong> ${data.answer}`;
                input.value = '';

                speakGreekText(data.answer);
            } catch (err) {
                alert(err.message);
                setVoiceStatus('', 'Σφάλμα');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Ερώτηση';
            }
        }

        /* --- READING & QUIZ --- */
        function prepareReadingView(data) {
            document.getElementById('result-title').textContent = data.title;
            currentSummaryPage = 0;

            const list = document.getElementById('takeaways-list');
            list.innerHTML = (data.key_takeaways || [])
                .map(item => `<div class="key-point-row"><span class="kp-dot"></span><span>${item}</span></div>`)
                .join('');

            renderSummaryPage(0);
            renderQuizQuestions(data.quiz);
        }

        function renderSummaryPage(pageIdx) {
            if (!summarySections.length) return;
            currentSummaryPage = pageIdx;
            const totalPages = summarySections.length;
            const sec = summarySections[pageIdx];

            document.getElementById('page-indicator').textContent = `Σελίδα ${pageIdx + 1} από ${totalPages}`;
            document.getElementById('sec-heading').textContent = `${pageIdx + 1}. ${sec.heading}`;
            document.getElementById('sec-explanation').textContent = sec.explanation;

            const exBox = document.getElementById('sec-example-box');
            if (sec.example && sec.example.trim()) {
                exBox.style.display = 'block';
                document.getElementById('sec-example').textContent = sec.example;
            } else {
                exBox.style.display = 'none';
            }

            const takeawaysWrapper = document.getElementById('takeaways-wrapper');
            takeawaysWrapper.style.display = (pageIdx === totalPages - 1) ? 'block' : 'none';

            document.getElementById('prev-page-btn').disabled = (pageIdx === 0);
            document.getElementById('next-page-btn').disabled = (pageIdx === totalPages - 1);

            const dotsContainer = document.getElementById('page-dots');
            dotsContainer.innerHTML = '';
            for (let i = 0; i < totalPages; i++) {
                const dot = document.createElement('button');
                dot.type = 'button';
                dot.className = 'page-dot' + (i === pageIdx ? ' active' : '');
                dot.title = `Σελίδα ${i + 1}`;
                dot.onclick = () => renderSummaryPage(i);
                dotsContainer.appendChild(dot);
            }
        }

        function changeSummaryPage(delta) {
            const nextIdx = currentSummaryPage + delta;
            if (nextIdx >= 0 && nextIdx < summarySections.length) {
                renderSummaryPage(nextIdx);
                document.getElementById('summary-sheet').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }

        function renderQuizQuestions(quizList) {
            currentQuizData = quizList;
            userSelections = {};
            isSubmitted = false;

            document.getElementById('next-steps-box').style.display = 'none';

            const scorePill = document.getElementById('score-display');
            scorePill.classList.remove('done');

            const submitBtn = document.getElementById('submit-quiz-btn');
            submitBtn.style.display = 'block';

            updateSelectionCounter();

            const quizContainer = document.getElementById('quiz-container');
            quizContainer.innerHTML = '';

            currentQuizData.forEach((q, qIdx) => {
                const block = document.createElement('div');
                block.className = 'question-block';
                block.id = `quiz-card-${qIdx}`;

                const qHeader = document.createElement('div');
                qHeader.className = 'q-header';
                qHeader.innerHTML = `<span class="q-index">0${qIdx + 1}</span><div class="q-text">${q.question}</div>`;
                block.appendChild(qHeader);

                const choicesDiv = document.createElement('div');
                choicesDiv.className = 'choices-grid';

                q.options.forEach((optText, optIdx) => {
                    const btn = document.createElement('button');
                    btn.className = 'choice-btn';
                    btn.innerHTML = `<span class="choice-letter">${LETTERS[optIdx] || optIdx + 1}</span><span>${optText}</span>`;
                    btn.onclick = () => {
                        if (isSubmitted) return;
                        userSelections[qIdx] = optIdx;

                        choicesDiv.querySelectorAll('.choice-btn').forEach(b => b.classList.remove('selected'));
                        btn.classList.add('selected');
                        updateSelectionCounter();
                    };
                    choicesDiv.appendChild(btn);
                });

                const rationale = document.createElement('div');
                rationale.className = 'q-rationale';
                rationale.id = `quiz-feedback-${qIdx}`;

                block.appendChild(choicesDiv);
                block.appendChild(rationale);
                quizContainer.appendChild(block);
            });
        }

        function updateSelectionCounter() {
            const selectedCount = Object.keys(userSelections).length;
            document.getElementById('score-display').textContent = `${selectedCount} / ${currentQuizData.length} επιλεγμένα`;
        }

        function submitQuiz() {
            const total = currentQuizData.length;
            const answeredCount = Object.keys(userSelections).length;

            if (answeredCount < total) {
                const proceed = confirm(`Έχεις απαντήσει σε ${answeredCount} από τις ${total} ερωτήσεις. Θέλεις να υποβάλεις το τεστ;`);
                if (!proceed) return;
            }

            isSubmitted = true;
            let score = 0;

            currentQuizData.forEach((q, qIdx) => {
                const block = document.getElementById(`quiz-card-${qIdx}`);
                const allBtns = block.querySelectorAll('.choice-btn');
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
                    feedback.innerHTML = `<strong>Σωστό.</strong> ${q.explanation}`;
                } else if (chosenIdx === undefined) {
                    feedback.innerHTML = `<strong>Δεν απαντήθηκε.</strong> Σωστή επιλογή: ${q.options[q.correct_index]}. ${q.explanation}`;
                } else {
                    feedback.innerHTML = `<strong>Λάθος.</strong> ${q.explanation}`;
                }
                feedback.style.display = 'block';
            });

            const scorePill = document.getElementById('score-display');
            scorePill.textContent = `Αποτέλεσμα: ${score} / ${total}`;
            scorePill.classList.add('done');

            document.getElementById('submit-quiz-btn').style.display = 'none';

            const nextBox = document.getElementById('next-steps-box');
            const nextMsg = document.getElementById('next-steps-msg');
            const retryBtn = document.getElementById('retry-btn');

            if (score === total) {
                nextMsg.innerHTML = `<strong>Άριστο αποτέλεσμα (${score}/${total}).</strong> Μπορείς να δοκιμάσεις ένα νέο σετ ερωτήσεων ή να συνεχίσεις με επόμενες σημειώσεις.`;
                retryBtn.style.display = 'none';
            } else {
                nextMsg.innerHTML = `<strong>Ολοκληρώθηκε με σκορ ${score}/${total}.</strong> Μπορείς να επαναλάβεις το ίδιο quiz, να δημιουργήσεις νέες ερωτήσεις ή να περάσεις στο επόμενο κεφάλαιο.`;
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
            btn.textContent = 'Δημιουργία...';

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
                alert(err.message);
            } finally {
                btn.disabled = false;
                btn.textContent = 'Νέες Ερωτήσεις';
            }
        }

        function startNextChapter() {
            stopSpeech();
            document.getElementById('notes-input').value = '';
            document.getElementById('file-input').value = '';
            updateFileName();
            activeNotesText = '';
            currentStudyData = null;
            summarySections = [];
            currentSummaryPage = 0;

            document.getElementById('results-area').style.display = 'none';
            document.getElementById('voice-area').style.display = 'none';
            document.getElementById('header-actions').style.display = 'none';
            document.getElementById('main-wrapper').classList.remove('active-study');
            document.getElementById('input-panel').style.display = 'block';

            window.scrollTo({ top: 0, behavior: 'smooth' });
            document.getElementById('notes-input').focus();
        }

        if ('speechSynthesis' in window) {
            window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
        }
    </script>
</body>
</html>
    """