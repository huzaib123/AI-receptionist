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

# 2. Create venv & install
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# → Edit .env: set LLM_API_KEY (free Gemini key) and, optionally, LLM_FALLBACK_API_KEY (free Groq key)
# → Optionally set Google Calendar variables
# → Optionally change ADMIN_API_KEY from the default

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
| `LLM_API_KEY`                 | *(required)*                  | Key for the primary provider (free Gemini key)  |
| `LLM_BASE_URL`                | Gemini OpenAI-compatible URL  | Any OpenAI-compatible endpoint                  |
| `LLM_MODEL_NAME`              | `gemini-3.5-flash-lite`       | Primary model name                              |
| `LLM_FALLBACK_API_KEY`        | `""`                          | Backup provider key (free Groq key); empty = no backup |
| `LLM_FALLBACK_BASE_URL`       | `https://api.groq.com/openai/v1` | Backup OpenAI-compatible endpoint            |
| `LLM_FALLBACK_MODEL_NAME`     | `llama-3.3-70b-versatile`     | Backup model, used when the primary errors or is rate-limited |
| `LLM_TEMPERATURE`             | `0.3`                         | Sampling temperature                           |
| `LLM_TIMEOUT_SECONDS`         | `30`                          | Per-request timeout                            |
| `OPENAI_API_KEY`              | `""`                          | Legacy: used with `gpt-4o-mini` only when `LLM_API_KEY` is empty |
| `LOG_LEVEL`                   | `INFO`                        | Python log level                               |
| `DATABASE_URL`                | `sqlite:///./receptionist.db` | Database URL (SQLite or PostgreSQL)             |
| `ADMIN_API_KEY`               | `dev_secret_key_123`          | API key for admin dashboard endpoints          |
| `CHAT_RATE_LIMIT_PER_MINUTE`  | `60`                          | Max chat requests per IP per minute             |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | `""`                          | Path to service account JSON (empty = stubs)   |
| `GOOGLE_CALENDAR_ID`          | `primary`                     | Target calendar ID                             |
| `BUSINESS_TIMEZONE`           | `Asia/Karachi`                | IANA timezone                                  |
| `BUSINESS_HOURS_START`        | `9`                           | Opening hour (24h)                             |
| `BUSINESS_HOURS_END`          | `19`                          | Closing hour (24h)                             |
| `BUSINESS_DAYS`               | `0,1,2,3,4,5`                 | Working days (0=Mon, 6=Sun)                    |
| `BOOKING_BUFFER_MINUTES`      | `15`                          | Gap between appointments                       |
| `DEFAULT_SLOT_WINDOW_DAYS`    | `14`                          | How far ahead to search                        |

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
3. Configure environment variables: `LLM_API_KEY`, `LLM_FALLBACK_API_KEY`, `ADMIN_API_KEY`, `DATABASE_URL`, `GOOGLE_SERVICE_ACCOUNT_FILE`, `GOOGLE_CALENDAR_ID`
4. Deploy — the Dockerfile compiles the React SPA, runs migrations, and starts the unified app

---

## Security

- **Admin auth**: All `/admin/*` endpoints require `X-Admin-API-Key` header. Change the default key before deploying.
- **Rate limiting**: In-memory per-IP limiter on `/chat` (default: 60 req/min). Exceeding returns HTTP 429.
- **CORS**: Configured to allow all origins in dev. Restrict `allow_origins` in production.
- **Secrets**: All credentials loaded from environment variables, never committed to git.
