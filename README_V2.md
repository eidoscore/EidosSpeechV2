# eidosSpeech v2

**Free Text-to-Speech API** — 1,200+ neural voices, 75+ languages.
Built with FastAPI, Docker, and Microsoft Edge TTS.

![License](https://img.shields.io/badge/License-MIT-green.svg) ![Python](https://img.shields.io/badge/Python-3.11-blue.svg) ![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)

---

## 🚀 Features

- **1,200+ Voices**: High-quality neural voices from Microsoft Edge.
- **75+ Languages**: Including Indonesian (Bahasa Indonesia), English, Japanese, etc.
- **Dual Interface**:
  - **Web UI**: User-friendly TTS tool with dark mode.
  - **REST API**: Simple POST endpoint for integration.
- **Smart Caching**: Identical requests are cached to disk (SHA256).
- **Rate Limiting**:
  - Anonymous: 5 req/day (Web UI only).
  - Registered: 30 req/day (API Key).
- **Proxy Support**: Round-robin rotation or direct connection.
- **Admin Panel**: Manage users, bans, and blacklists.

---

## 🛠️ Quick Start (Local)

### Prerequisites
- Python 3.11+
- git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/eidosspeech-v2.git
   cd eidosspeech-v2
   ```

2. **Create environment file**
   Copy `.env.example` to `.env` and update the `SECRET_KEY` and `ADMIN_KEY`.
   ```bash
   cp .env.example .env
   ```
   > **Note**: For local dev, you can skip configuring email/SMTP. The verification token will be printed to the console logs.

3. **Install dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Run the server**
   ```bash
   python run.py
   ```
   Access the app at: `http://localhost:8000`

---

## 🐳 Deployment (Docker)

Recommended for production.

1. **Configure `.env`**
   Ensure `APP_ENV=production` and `SECRET_KEY` is secure.

2. **Build and Run**
   ```bash
   docker compose up -d --build
   ```

3. **Verify**
   ```bash
   curl http://localhost:8000/api/v1/health
   # {"status":"ok", ...}
   ```

---

## 📚 API Documentation

Interactive docs available at `/docs` (Swagger UI) or `/api-docs` (Custom UI).

### Generate Speech
```bash
curl -X POST http://localhost:8000/api/v1/tts \
  -H "X-API-Key: esk_your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world from eidosSpeech!",
    "voice": "en-US-JennyNeural"
  }' --output audio.mp3
```

### List Voices
```bash
curl "http://localhost:8000/api/v1/voices?language=id-ID"
```

---

## 🛡️ Admin Panel

Access `/admin` and enter your `ADMIN_KEY` (configured in `.env`).

- **Dashboard**: View active users, request stats, and cache usage.
- **User Management**: Search users, view API keys, ban/unban.
- **Blacklist**: Block malicious IPs or emails permanently.

---

## 🧩 Project Structure

```
eidosspeech-v2/
├── app/
│   ├── api/          # API routes (v1, auth, admin)
│   ├── core/         # Config, security, rate limiter
│   ├── db/           # Database models & engine
│   ├── services/     # Email, Proxy, TTS engine
│   ├── static/       # Frontend HTML/JS/CSS
│   └── main.py       # App entry point
├── data/             # Persistent storage (DB, Cache)
├── docsv2/           # Architecture docs
├── .env.example      # Environment template
├── Dockerfile
└── requirements.txt
```

---

## 📄 License

MIT License. Free to use and modify.
Powered by eidosStack.
