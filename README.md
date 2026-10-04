 Aura — Intelligent AI Receptionist

Aura is a professional, conversational AI receptionist built for modern service businesses (clinics, salons, wellness studios, and co-working spaces). By blending natural language understanding with direct system integrations, Aura automates appointment booking, handles client inquiries with human-like warmth, and uses machine learning to predict and minimize no-show risks.

Built using **FastAPI**, **LangChain**, **React**, **Google Calendar API**, and a custom **Scikit-Learn** predictive pipeline.

---

## Selling Aura to local businesses

Aura is packaged as a **Website + AI Receptionist** combo for SMBs (clinics, dental, salons, gyms, tuition centres, vets, professional firms).

| What | Where |
|---|---|
| Public sales page + live, personalised demo (no backend needed) | `docs/index.html`, deployed to GitHub Pages by `.github/workflows/pages.yml` |
| Personalised demo link per prospect | `…/?biz=dental&name=Smile%20Life%20Dental` (`biz` = clinic, dental, beauty, fitness, tuition, pets, services) |
| Per-client branding, services, RM prices, hours, FAQ, WhatsApp | `config/business_profile.json` (copy from `config/business_profile.example.json`) |
| Add the chatbot to a client's **existing** website | `<script src="https://YOUR-AURA-HOST/widget.js" defer></script>` |
| Lead list + outreach emails | `sales/` (gitignored — keep prospect data out of the public repo) |

Each client deployment is one container with its own `.env` and `business_profile.json`.
The agent replies in the customer's language (EN / BM / 中文), quotes prices in RM, and hands off to WhatsApp via the `handoff_to_human` tool when it can't help.

---

## Architecture

```
ai-receptionist/
├── app/
│   ├── main.py                  # FastAPI entry‑point
│   ├── core/
│   │   ├── settings.py          # Env‑var config (LLM, Calendar, Business, DB, Security)
│   │   └── security.py          # Admin auth & rate limiting
│   ├── db/
│   │   ├── session.py           # Engine + session management
│   │   ├── models.py            # SQLAlchemy models (Customer, Booking)
│   │   └── crud.py              # Querying and stats helpers
│   ├── ml/
│   │   ├── no_show_model.py     # Production loader and risk predictor
│   │   └── no_show_pipeline.joblib  # Trained model (gitignored)
│   ├── agent/
│   │   ├── agent.py             # LangChain tool‑calling agent
│   │   └── tools.py             # Tools connected to DB, GCal, and ML predictor
│   ├── integrations/
│   │   └── google_calendar.py   # Google Calendar v3 API client
│   ├── llm/
│   │   └── chat.py              # Plain LangChain chat (legacy)
│   └── schemas/
│       ├── chat.py              # Pydantic request / response models
│       └── ml.py                # Pydantic ML schemas
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # React SPA (landing, chat, admin dashboard)
│   │   └── index.css            # Design system
│   ├── vite.config.js           # Vite config with API proxy
│   └── package.json
├── ml/
│   ├── train.py                 # Download, preprocess, and train ML model
│   └── model_card.md            # ML model details and metrics
├── tests/
│   ├── conftest.py              # In-memory database patcher
│   ├── test_db.py               # Database and CRUD unit tests
│   ├── test_admin.py            # Admin endpoint integration tests
│   ├── test_ml.py               # ML prediction unit and route tests
│   ├── test_tools.py            # Tool unit tests
│   └── test_google_calendar.py  # Calendar unit + integration tests
├── alembic/                     # Alembic migrations
├── Dockerfile                   # Multi-stage build (Node + Python)
├── docker-compose.yml           # App + PostgreSQL
├── .env.example                 # Template for configuration
└── requirements.txt
```

---

## Quick Start

```bash
# 1. Clone & enter the project
cd ai-receptionist

# 2. Create venv & install (needs Python 3.10 or newer; 3.12 recommended)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# → Edit .env: set LLM_API_KEY (free Groq key; the backup model reuses it)
# → Optionally set Google Calendar variables
# → Set ADMIN_API_KEY to a long random value to turn on the admin endpoints

# 4. Train the ML model (first time only)
python ml/train.py

# 5. Initialize Database
alembic upgrade head

# 6. Build frontend & start
cd frontend && npm install && npm run build && cd ..
cp -r frontend/dist/ app/static/
uvicorn app.main:app --reload

# 7. Open http://localhost:8000
```

---

## Frontend

The frontend is a React SPA built with Vite, featuring:

- **Landing page** — explains the product with animated sections
- **Chat widget** — floating button that opens a conversation with the AI agent
- **Admin dashboard** — protected by API key; shows bookings, stats, and breakdowns

### Development mode (hot reload)

```bash
# Terminal 1: Backend
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend (proxies API calls to :8000)
cd frontend && npm run dev -- --port 5173
```

### Production mode (unified)

```bash
cd frontend && npm run build && cd ..
cp -r frontend/dist/ app/static/
uvicorn app.main:app --port 8000
# → Visit http://localhost:8000
```

---

## Database Setup & Migrations

By default, the application runs on a local **SQLite** database (`receptionist.db`). Tables are automatically created at startup.

### Using PostgreSQL

```env
DATABASE_URL=postgresql://username:password@localhost:5432/dbname
```

### Managing Migrations (Alembic)

```bash
alembic revision --autogenerate -m "Add new column"
alembic upgrade head
```

---

## Google Calendar Setup

### 1. Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the **Google Calendar API** under **APIs & Services → Library**

### 2. Create a Service Account

1. **APIs & Services → Credentials → Create Credentials → Service account**
2. Download the JSON key file and save it (e.g. `credentials/service-account.json`)

### 3. Share Your Calendar

1. Open [Google Calendar](https://calendar.google.com)
2. Share the target calendar with the service account's email (`client_email` in the JSON)
3. Set permission to **Make changes to events**

### 4. Configure

```env
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service-account.json
GOOGLE_CALENDAR_ID=primary
BUSINESS_TIMEZONE=Asia/Karachi
```

> **No credentials?** No problem — the app falls back to stub data automatically.

---

## Configuration Reference

| Variable                      | Default                       | Description                                    |
|-------------------------------|-------------------------------|------------------------------------------------|
| `LLM_API_KEY`                 | *(required)*                  | Key for the main provider (free Groq key)       |
| `LLM_BASE_URL`                | `https://api.groq.com/openai/v1` | Any OpenAI-compatible endpoint               |
| `LLM_MODEL_NAME`              | `openai/gpt-oss-120b`         | Main model name                                 |
| `LLM_FALLBACK_API_KEY`        | `""`                          | Backup provider key; empty = reuse `LLM_API_KEY` on the same provider |
| `LLM_FALLBACK_BASE_URL`       | `https://api.groq.com/openai/v1` | Backup OpenAI-compatible endpoint            |
| `LLM_FALLBACK_MODEL_NAME`     | `openai/gpt-oss-20b`          | Backup model, used when the main one errors or is rate-limited; `none` = off |
| `LLM_REASONING_EFFORT`        | `""`                          | `low`/`medium`/`high`; empty = `low` for gpt-oss models, not sent to others |
| `LLM_LOCAL_BASE_URL`          | `""`                          | Last-resort backup on your own machine (Ollama: `http://localhost:11434/v1`); empty = off |
| `LLM_LOCAL_MODEL_NAME`        | `qwen3:8b`                    | Local backup model                              |
| `LLM_LOCAL_API_KEY`           | `ollama`                      | Any value works for Ollama                      |
| `LLM_LOCAL_TIMEOUT_SECONDS`   | `90`                          | Local models are slower; allow longer replies   |
| `LLM_LOCAL_SYSTEM_SUFFIX`     | `/no_think`                   | Added to the local model's prompt; stops Qwen3's slow thinking step; empty for other models |
| `LLM_TEMPERATURE`             | `0.3`                         | Sampling temperature                           |
| `LLM_TIMEOUT_SECONDS`         | `30`                          | Per-request timeout                            |
| `OPENAI_API_KEY`              | `""`                          | Legacy: used with `gpt-4o-mini` only when `LLM_API_KEY` is empty |
| `LOG_LEVEL`                   | `INFO`                        | Python log level                               |
| `DATABASE_URL`                | `sqlite:///./receptionist.db` | Database URL (SQLite or PostgreSQL)             |
| `ADMIN_API_KEY`               | `""`                          | Admin API key; admin endpoints are off until it is 24+ characters |
| `CHAT_RATE_LIMIT_PER_MINUTE`  | `15`                          | Max chat requests per visitor IP per minute     |
| `CHAT_DAILY_LIMIT_PER_IP`     | `200`                         | Max chat requests per visitor IP per day        |
| `CHAT_GLOBAL_LIMIT_PER_MINUTE`| `40`                          | Max chat requests per minute across all visitors (protects the LLM quota) |
| `TRUSTED_PROXY_IPS`           | `127.0.0.1,::1`               | Proxies (e.g. cloudflared) whose forwarded-IP header is trusted |
| `CORS_ALLOW_ORIGINS`          | `*`                           | Origins allowed to call the API (no cookies are used) |
| `ENABLE_API_DOCS`             | `false`                       | Serve `/docs` and `/redoc`                      |
| `MAX_CHAT_SESSIONS`           | `2000`                        | Chat sessions kept in memory                    |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | `""`                          | Path to service account JSON (empty = stubs)   |
| `GOOGLE_CALENDAR_ID`          | `primary`                     | Target calendar ID                             |
| `BUSINESS_TIMEZONE`           | `Asia/Karachi`                | IANA timezone                                  |
| `BUSINESS_HOURS_START`        | `9`                           | Opening hour (24h)                             |
| `BUSINESS_HOURS_END`          | `19`                          | Closing hour (24h)                             |
| `BUSINESS_DAYS`               | `0,1,2,3,4,5`                 | Working days (0=Mon, 6=Sun)                    |
| `BOOKING_BUFFER_MINUTES`      | `15`                          | Gap between appointments                       |
| `DEFAULT_SLOT_WINDOW_DAYS`    | `14`                          | How far ahead to search                        |

### Mac backup with Ollama (free, runs on your own machine)

When both Groq models hit their free limits, Aura can answer from a model on your own Mac instead of making customers wait.

1. Install Ollama from https://ollama.com/download and run `ollama pull qwen3:8b` (about 5 GB; fits a 16 GB Mac).
2. If the backend runs on the same Mac, set `LLM_LOCAL_BASE_URL=http://localhost:11434/v1` (inside Docker: `http://host.docker.internal:11434/v1`).
3. If the backend runs on a server, don't expose Ollama directly: it has no password, so anyone with the tunnel address could use your Mac. Run the backend on the Mac instead (step 2) and tunnel the backend (`cloudflared tunnel --url http://localhost:8000`).
4. Keep the Mac awake and plugged in (System Settings → Battery → prevent sleeping when the display is off). If the Mac is off, Aura still runs on Groq; only the last backup is missing.

A Mac handles about one conversation at a time, with replies in 5–15 seconds.

---

## Running Tests

```bash
source .venv/bin/activate

# All unit + route tests (no credentials needed, in-memory DB)
python -m pytest tests/ -v -k "not integration"

# Google Calendar integration tests (require real credentials)
python -m pytest tests/test_google_calendar.py -v -m integration
```

---

## API Endpoints

### `GET /health`
Returns `{"status": "ok"}`.

### `POST /chat`

```json
// Request
{"message": "I'd like to book a haircut for tomorrow at 3 PM", "session_id": "optional"}

// Response
{"reply": "I found some available slots...", "tools_called": ["calendar_list_slots"], "usage": null}
```

### `GET /admin/bookings/today`
**Header:** `X-Admin-API-Key: <your key>`

Returns today's bookings with customer details.

### `GET /admin/stats`
**Header:** `X-Admin-API-Key: <your key>`

Returns aggregated booking stats, service breakdown, and system metrics.

### `POST /ml/no_show`

```json
// Request
{"age": 30, "days_until_appointment": 5, "past_no_shows": 1, "appointment_hour": 14, "day_of_week": 1}

// Response
{"no_show_probability": 0.186, "risk_level": "medium"}
```

Interactive API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Docker Deployment

### Docker Compose (recommended)

```bash
# Set your environment variables in .env
docker-compose up --build
```

This launches:
1. A **PostgreSQL** database on port `5432`
2. The **unified app** on port `8000` (FastAPI + React SPA)
3. Alembic migrations run automatically on startup

### Cloud Deployment (Render / Railway / VPS)

1. Connect your GitHub repository
2. Select **Docker** as the environment
3. Configure environment variables: `LLM_API_KEY`, `ADMIN_API_KEY`, `DATABASE_URL`, `GOOGLE_SERVICE_ACCOUNT_FILE`, `GOOGLE_CALENDAR_ID`
4. Deploy — the Dockerfile compiles the React SPA, runs migrations, and starts the unified app

---

## Security

- **Admin auth**: `/admin/*` needs the `X-Admin-API-Key` header, compared in constant time. The endpoints stay off (503) until `ADMIN_API_KEY` is 24+ characters, and 10 wrong keys from one IP lock it out for an hour.
- **Rate limiting**: `/chat` is limited per visitor per minute and per day, plus a shared cap across all visitors so a flood can't use up the LLM quota. Behind Cloudflare Tunnel the real visitor IP comes from `CF-Connecting-IP`, trusted only from `TRUSTED_PROXY_IPS`.
- **Input limits**: request bodies over 16 KB are refused, messages are capped at 1,000 characters, session ids at 64 safe characters, and at most `MAX_CHAT_SESSIONS` sessions are kept in memory.
- **Errors**: provider and database errors are logged on the server only; visitors get a plain message.
- **Headers**: `nosniff`, `X-Frame-Options: DENY`, HSTS, a strict CSP on API responses and a locked-down `Permissions-Policy`.
- **CORS**: any origin may call the API so the widget works on client sites; credentials are off because no cookies are used.
- **API docs**: `/docs` is off unless `ENABLE_API_DOCS=true`.
- **Secrets**: All credentials loaded from environment variables, never committed to git.
