# Cognify — AI-Powered Digital Twin Cognitive Assessment Platform

A full-stack web application that measures cognitive performance through interactive tests and generates AI-powered insights using Llama 3.3 via Groq API.

![Cognify](https://img.shields.io/badge/Flask-Python-blue) ![AI](https://img.shields.io/badge/AI-Llama%203.3-green) ![Status](https://img.shields.io/badge/Status-Live-brightgreen)

## Features

- **User Authentication** — Register, login, profile photo upload
- **3 Cognitive Tests** — Memory (adaptive difficulty), Reaction Time, Attention
- **AI Insights** — Personalized analysis via Groq API + Llama 3.3
- **Digital Twin** — Predicts next session performance from last 5 sessions
- **Gamification** — Daily streaks, 8 unlockable badges
- **Dashboard** — Chart.js graphs, fatigue detection, leaderboard
- **Cognitive Profile** — Rates Memory, Reaction, Attention as Excellent/Good/Average

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript, Chart.js |
| Backend | Python Flask |
| Database | SQLite (local) / PostgreSQL (production) |
| AI | Groq API + Llama 3.3 70B |
| Auth | Flask-Bcrypt password hashing |
| Deployment | Render |

## Setup

```bash
# Clone the repo
git clone https://github.com/yourusername/cognify.git
cd cognify

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "GROQ_API_KEY=your_key_here" > .env
echo "SECRET_KEY=your_secret_here" >> .env

# Run the app
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

## Project Structure

```
cognify/
├── app.py              # Flask backend — routes, API, logic
├── requirements.txt    # Python dependencies
├── Procfile            # Render deployment config
├── static/
│   └── uploads/        # Profile photos
└── templates/
    ├── index.html      # Main tests page
    ├── dashboard.html  # Analytics dashboard
    ├── login.html      # Login page
    ├── register.html   # Registration page
    └── profile.html    # User profile
```

## Live Demo

[cognify.onrender.com](https://cognify.onrender.com)

---
Built as a placement project demonstrating full-stack development, AI/ML integration, and data analytics.
