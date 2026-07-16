<div align="center">

# 🛡️ SentinelAI

### An AI copilot that watches your system's activity, judges what's safe and what's not, and protects your files — automatically.

[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://sentinelai-frontend-u2ts.onrender.com)
[![API Docs](https://img.shields.io/badge/API-docs-blue)](https://sentinelai-backend-rdwp.onrender.com/docs)
[![Python](https://img.shields.io/badge/backend-Python%20%2F%20FastAPI-3776AB)](https://www.python.org/)
[![React](https://img.shields.io/badge/frontend-React%20%2F%20Vite-61DAFB)](https://react.dev/)

**[🌐 Try the live app](https://sentinelai-frontend-u2ts.onrender.com)** · **[📖 API documentation](https://sentinelai-backend-rdwp.onrender.com/docs)**

</div>

---

## What is this, really?

Imagine you had a security guard who never sleeps. Every few seconds, they check what's happening on your computer — who's logging in, which files are being touched, whether anything looks unusual. If something seems dangerous, they don't just make a note of it — they lock away the sensitive files themselves, right away. And if you ever want to ask "hey, has anything weird happened today?", you can just *ask* them, in plain English, and get a straight answer.

That's SentinelAI. Except the guard isn't a person — it's a combination of automation scripts and machine learning models working together, watching in the background, all the time.

You don't need to know anything about AI or cybersecurity to understand the dashboard. Green means calm. Amber means "keep an eye on this." Red means "something needs attention." That's really the whole idea.

---

## Why does this exist?

Small teams and individual developers rarely have a dedicated security analyst sitting around, reading logs all day. Most of the time, suspicious activity just goes unnoticed until it's too late. SentinelAI is an attempt at solving that in miniature — a system that watches, thinks, and reacts on its own, instead of waiting for a human to check.

---

## How it actually works, in four steps

1. **Watch** — A background job checks for new activity (logins, file access, system events) every 15 seconds, without anyone clicking a button.
2. **Think** — Each new event is run through a machine learning pipeline that decides: is this Normal, Suspicious, or Critical?
3. **Act** — If something is flagged as Critical and it involves a real file, the system automatically encrypts that file to protect it — no human needed in the loop.
4. **Explain** — Everything is shown live on a dashboard, and you can ask an AI chat assistant questions about it in plain English, and it'll answer using the real data, not guesses.

---

## Features

### 🤖 Machine Learning — 10 techniques, working together

Rather than relying on just one algorithm, SentinelAI trains multiple models on the same data, compares how well each one performs, and automatically picks the best one for the job — a real applied machine learning practice.

| Technique | What it's used for |
|---|---|
| K-Nearest Neighbors (Classification) | Classifying events by comparing them to similar past events |
| K-Nearest Neighbors (Regression) | Estimating a numeric "risk score" for each event |
| Linear Regression | Predicting risk scores, and separately, forecasting future risk trends over time |
| Logistic Regression (Binary) | A simple yes/no check — is this event anomalous at all? |
| Logistic Regression (Multiclass) | Sorting events into Normal / Suspicious / Critical |
| Decision Tree | Classifying events, and explaining *why* a decision was made in plain language |
| Artificial Neural Network | Learning more complex, non-linear patterns in the data |
| Support Vector Machine | Another classification approach, compared against the others |
| K-Means Clustering | Grouping similar behavior patterns together, without being told what "normal" means |
| Random Forest | Combining many decision trees into one stronger, more reliable classifier |

### ⚙️ Automation — real background work, not simulations

| Module | What it does |
|---|---|
| Log Monitoring | Continuously reads and analyzes new activity, every 15 seconds |
| File Backup & Compression | Automatically zips and archives files, and cleans up old backups on its own |
| File Encryption & Decryption | Locks away sensitive files using industry-standard encryption, and verifies nothing was tampered with |
| File Management | Organizes and tracks every file the system touches |
| AI Chatbot | A conversational assistant that answers questions using real, live data — not guesses |

### 🖥️ Dashboard

- **Live Feed** — a real-time stream of everything the system has seen, color-coded by risk
- **Try the classifier live** — type any activity description and watch the AI classify it instantly
- **Risk Trend** — a chart of risk over time, plus a short-term forecast
- **Behavior Clusters** — groups of similar activity, discovered automatically by the AI
- **Security Copilot** — a chat assistant you can ask questions to
- **File Vault** — back up or encrypt any file with one click

---

## How it's built

**Backend:** Python, FastAPI, SQLAlchemy, scikit-learn, APScheduler (for the background jobs), Google Gemini API (for the chatbot)

**Frontend:** React, Vite, Tailwind CSS, Recharts, Framer Motion

**Architecture:** The backend is organized into clear layers — API routes, business logic ("services"), and the ML pipeline are all kept separate, so each piece can be understood, tested, and changed on its own without breaking the rest.

```
sentinelai/
├── backend/
│   ├── app/
│   │   ├── api/          → the routes the frontend talks to
│   │   ├── services/      → the actual automation logic (backups, encryption, logs, chat)
│   │   ├── ml/            → training, prediction, and the saved models
│   │   ├── models.py      → database structure
│   │   ├── schemas.py     → what data looks like coming in and going out
│   │   └── main.py        → where everything gets wired together
│   └── sample_data/        → a demo file to try the File Vault with
│
└── frontend/
    └── src/
        ├── components/    → each dashboard panel (Live Feed, Chat, etc.)
        └── App.jsx         → the main dashboard layout
```

---

## Try it yourself

You don't need to install anything — the live version is right here:

👉 **[sentinelai-frontend-u2ts.onrender.com](https://sentinelai-frontend-u2ts.onrender.com)**

A couple of things worth knowing:
- This runs on a free hosting tier, so if nobody has visited in a while, it may take **30–50 seconds** to wake up the first time. That's normal — just give it a moment.
- To try the **File Vault**, use this path, which points to a sample file included in the repo:
  ```
  sample_data/demo_document.txt
  ```

---

## Running it on your own machine

<details>
<summary><b>Click to expand setup instructions</b></summary>

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# then fill in .env with your own values (see below)

python -m app.ml.train_models   # trains all 10 ML models, takes under a minute
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Environment variables you'll need

| Variable | What it's for |
|---|---|
| `SECRET_KEY` | Used to sign login tokens — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `FERNET_KEY` | Used to encrypt files — generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `GEMINI_API_KEY` | Powers the AI chatbot — get a free key at [aistudio.google.com](https://aistudio.google.com) |

Full details are in `backend/.env.example`.

</details>

---

## A note on the data

The events you see are generated by a realistic simulation, not real network traffic — this is a common and honest approach when building and demonstrating a machine learning pipeline without access to live production data. The scoring logic, the noise, and the class imbalance are all deliberately designed to mirror what real security data tends to look like, so the models are being tested fairly rather than on an easy, artificial dataset.

You can also try the **"Try the classifier live"** box on the dashboard to type your own custom activity description and see the model classify it in real time — a genuine, hands-on way to test the AI yourself.

---

## Author

**Kazi Anas Abdul Gaffar**
Computer Science and Engineering
SAL Institute of Technology and Engineering Research

Built as an extension of the Skill Based Training in *Python for Automation* and *Python for Machine Learning*, conducted by EduPyramids in collaboration with the Spoken Tutorial Project, IIT Bombay.

---

<div align="center">

If you found this interesting, a ⭐ on the repo is always appreciated.

</div>