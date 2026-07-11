# AgriGenie AI – Smart Farming Advice Agent

<div align="center">
  <h1>🌾 AgriGenie AI</h1>
  <p><strong>AI-Powered Smart Farming Advice Agent for Indian Agriculture</strong></p>
  <p>Powered by IBM watsonx.ai Granite Models · RAG Knowledge Base · Flask Backend</p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
    <img src="https://img.shields.io/badge/Flask-3.0-green?logo=flask" alt="Flask">
    <img src="https://img.shields.io/badge/IBM-watsonx.ai-be95ff?logo=ibm" alt="IBM">
    <img src="https://img.shields.io/badge/RAG-FAISS/ChromaDB-orange" alt="RAG">
    <img src="https://img.shields.io/badge/License-MIT-brightgreen" alt="MIT">
  </p>
</div>

---

## 🚀 Quick Start (3 Steps)

### Step 1 – Clone and Setup Environment

```bash
git clone <your-repo-url>
cd "AgriGenie AI – Smart Farming Advice Agent"

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

> If you want to use the optional ChromaDB vector backend on Windows, install Microsoft C++ Build Tools first, then run:
> `pip install chromadb==0.6.3`

### Step 2 – Configure IBM watsonx.ai Credentials

```bash
# Copy the example file
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/Mac
```

**Edit `.env` and update these 4 values:**

```env
IBM_API_KEY=your_ibm_cloud_api_key_here
IBM_PROJECT_ID=your_watsonx_project_id_here
IBM_URL=https://us-south.ml.cloud.ibm.com
IBM_MODEL_ID=ibm/granite-3-2-8b-instruct
```

> **How to get IBM credentials:**
> 1. Go to [IBM Cloud](https://cloud.ibm.com) → Create free account
> 2. Search "Watson Machine Learning" → Create instance
> 3. Get API Key: Manage → API Keys → Create
> 4. Get Project ID: [watsonx.ai](https://dataplatform.cloud.ibm.com) → New Project → Settings

### Step 3 – Run the Application

```bash
python app.py
```

Open browser: **http://localhost:5000**

---

## 🌟 Features

### 🤖 AI Features (IBM watsonx.ai + RAG)
| Feature | Description |
|---------|-------------|
| 💬 **AI Chat Advisor** | Conversational farming advisor with memory |
| 🌱 **Crop Recommendation** | Location/soil/season-specific crop selection |
| 🪨 **Soil Health Analysis** | pH, NPK, micronutrient analysis with correction advice |
| 🌤 **Weather Advisory** | Weather-based farming decisions and scheduling |
| 🧪 **Fertilizer Advisor** | Precise NPK schedules with organic alternatives |
| 🐛 **Pest & Disease Diagnosis** | Symptom-based pest ID + IPM treatment plan |
| 💧 **Irrigation Planner** | Smart irrigation scheduling and water-saving guide |
| 📊 **Mandi Price Analysis** | Market intelligence + sell/hold recommendations |
| 🏛 **Govt Schemes Advisor** | PM-KISAN, PMFBY, KCC eligibility and application guide |
| 📅 **Farming Calendar** | Monthly operations advisory for all crops |

### 🏗 Technical Features
| Feature | Details |
|---------|---------|
| 🔍 **RAG Pipeline** | FAISS (default) or ChromaDB vector store |
| 📚 **Knowledge Base** | 9 agricultural domain documents (crops, soil, pest, fertilizer, irrigation, weather, schemes, mandi, calendar) |
| 👤 **User Management** | Login, register, farmer profile |
| 📜 **Chat History** | Searchable, filterable history with re-ask feature |
| 📥 **PDF Reports** | Downloadable farming reports for any advisory |
| 🌙 **Dark Mode** | Full dark/light theme toggle |
| 📱 **Responsive** | Mobile-first Bootstrap 5 design |
| 🔒 **Secure** | CSRF protection, password hashing, session management |

---

## 📁 Project Structure

```
AgriGenie AI – Smart Farming Advice Agent/
├── app.py                      ← Flask application (main)
├── rag_pipeline.py             ← RAG pipeline (FAISS/ChromaDB)
├── requirements.txt            ← Python dependencies
├── .env.example                ← Environment template
├── .env                        ← Your credentials (NOT in repo – create from .env.example)
│
├── knowledge_base/             ← Agricultural knowledge documents
│   ├── crop_guides.txt         ← Major crop cultivation guides
│   ├── soil_health.txt         ← Soil testing and management
│   ├── fertilizer_recommendations.txt
│   ├── pest_disease_management.txt
│   ├── irrigation_practices.txt
│   ├── weather_advisories.txt
│   ├── government_schemes.txt
│   ├── mandi_market_info.txt
│   └── farming_calendar.txt
│
├── templates/                  ← Jinja2 HTML templates
│   ├── base.html               ← Layout with sidebar, topbar
│   ├── index.html              ← Landing page
│   ├── auth.html               ← Login / Register
│   ├── dashboard.html          ← Main dashboard
│   ├── chat.html               ← AI chat interface
│   ├── profile.html            ← Farmer profile
│   ├── crop_advisor.html       ← Crop recommendation
│   ├── soil_health.html        ← Soil analysis
│   ├── weather.html            ← Weather advisory
│   ├── fertilizer.html         ← Fertilizer recommendation
│   ├── pest_advisor.html       ← Pest & disease advisor
│   ├── irrigation.html         ← Irrigation planner
│   ├── mandi_prices.html       ← Market prices dashboard
│   ├── govt_schemes.html       ← Government schemes
│   ├── farming_calendar.html   ← Farming calendar
│   ├── chat_history.html       ← Chat history viewer
│   └── error.html              ← Error pages
│
├── static/
│   ├── css/main.css            ← Custom styles (dark mode, responsive)
│   └── js/main.js              ← Frontend JavaScript
│
├── instance/                   ← SQLite database (auto-created)
├── reports/                    ← Generated PDF reports
└── uploads/                    ← User uploads
```

---

## ⚙️ Configuration Reference

All configuration is in `.env`. Here's the complete reference:

```env
# IBM watsonx.ai (REQUIRED)
IBM_API_KEY=your_api_key
IBM_PROJECT_ID=your_project_id
IBM_URL=https://us-south.ml.cloud.ibm.com
IBM_MODEL_ID=ibm/granite-3-2-8b-instruct

# Flask
FLASK_SECRET_KEY=change-this-in-production
FLASK_PORT=5000
FLASK_DEBUG=False

# RAG
VECTOR_STORE=faiss           # Options: faiss | chroma
CHUNK_SIZE=512
CHUNK_OVERLAP=64
TOP_K_RESULTS=5

# Weather (optional)
OPENWEATHER_API_KEY=         # Leave blank for demo data
DEFAULT_LOCATION=New Delhi, IN
```

### Available IBM Granite Models

| Model ID | Tokens | Best For |
|----------|--------|----------|
| `ibm/granite-3-3-8b-instruct` | 128K | **Recommended** – Best for farming advice |
| `ibm/granite-3-2-8b-instruct` | 128K | Alternative 8B model |
| `ibm/granite-3-8b-instruct` | 4096 | Faster response |
| `ibm/granite-13b-instruct-v2` | 8K | Larger model |

---

## 🤖 Customizing Agent Behavior

Edit the `AGENT_INSTRUCTIONS` section at the top of [`app.py`](app.py) (around line 55):

```python
AGENT_INSTRUCTIONS = """
You are AgriGenie, an expert AI farming advisor...

PERSONA & TONE:
- Speak like a trusted local agronomist
- Use simple language for all education levels
...

SAFETY RULES:
- Always recommend PPE for pesticides
- Do not recommend banned chemicals
...
"""
```

**Customizable areas:**
- 🗣 **Tone**: Formal/casual, local language preference
- 🌾 **Specialization**: Specific crops, regions, organic farming focus
- 🌐 **Language**: Change preferred response language (Hindi, Telugu, etc.)
- ⚠️ **Safety**: Custom safety rules and disclaimers
- 📋 **Response Style**: Length, format, structure preferences
- 🇮🇳 **Indian Focus**: State-specific practices, MSP references

---

## 🔬 RAG Knowledge Base

### Adding Custom Documents

1. Create a `.txt` file in the `knowledge_base/` folder
2. Write your content in plain text
3. Restart the app (index will rebuild automatically)

```bash
# Or force rebuild via API
curl -X POST http://localhost:5000/api/rag-rebuild \
  -H "X-CSRFToken: <token>"
```

### Supported Formats
- `.txt` (recommended)
- `.md` (Markdown)

### Knowledge Base Topics
| File | Content |
|------|---------|
| `crop_guides.txt` | Wheat, Rice, Maize, Cotton, Soybean, Potato, Tomato cultivation |
| `soil_health.txt` | pH management, NPK, micronutrients, biofertilizers |
| `fertilizer_recommendations.txt` | Crop-wise NPK doses, organic alternatives |
| `pest_disease_management.txt` | FAW, BPH, rust, blight, IPM solutions |
| `irrigation_practices.txt` | Drip, sprinkler, flood irrigation guides |
| `weather_advisories.txt` | Monsoon, drought, flood, heat wave advisories |
| `government_schemes.txt` | PM-KISAN, PMFBY, SHC, KCC, e-NAM, PKVY |
| `mandi_market_info.txt` | Price systems, storage, FPO, export guides |
| `farming_calendar.txt` | Month-by-month operations for all crops |

---

## 🏃‍♂️ Running in Production

### Using Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

### Using Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:create_app()"]
```

```bash
docker build -t agrigenie .
docker run -p 5000:5000 --env-file .env agrigenie
```

### Environment Variables for Production

```env
FLASK_DEBUG=False
FLASK_SECRET_KEY=<strong-random-key>  # Use: python -c "import secrets;print(secrets.token_hex(32))"
```

---

## 🗃 Database

AgriGenie uses **SQLite** (default). Tables:
- `users` – Login accounts
- `farmer_profiles` – Farm details (location, soil, crops, land size)
- `chat_messages` – All AI conversations
- `crop_analyses` – Saved crop recommendations
- `soil_analyses` – Saved soil analysis reports

**Database location**: `instance/agrigenie.db`

To reset database:
```bash
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.drop_all(); db.create_all(); print('Reset done')"
```

---

## 🧪 Testing API Endpoints

```bash
# Test AI Chat (requires login session)
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: <token>" \
  -d '{"message": "What is the best crop for Punjab in Rabi season?", "topic": "crop"}'

# Get Mandi Prices (requires login session)
curl http://localhost:5000/api/mandi-prices

# RAG Status
curl http://localhost:5000/api/rag-status
```

---

## 🌐 Screenshots

| Page | Description |
|------|-------------|
| 🏠 Dashboard | Weather widget, mandi prices, quick actions, recent chats |
| 💬 AI Chat | Full-screen chat with topic selector and quick prompts |
| 🌱 Crop Advisor | Form + AI recommendation with cultivation guide |
| 🪨 Soil Health | pH slider, nutrient status, AI soil analysis |
| 🐛 Pest Advisor | Symptom tags, IPM-based treatment plan |
| 📊 Mandi Prices | Live price grid + AI sell/hold analysis |
| 📅 Calendar | Monthly operations calendar with AI advisory |

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/organic-farming-module`
3. Add knowledge base documents and/or new advisor routes
4. Update `AGENT_INSTRUCTIONS` for new domain
5. Submit Pull Request

---

## 📜 License

MIT License – Free to use for farming and agricultural purposes.

---

## 🙏 Acknowledgements

- **IBM watsonx.ai** – Granite LLM models for agricultural intelligence
- **FAISS** (Facebook AI) – Efficient vector similarity search
- **LangChain** – RAG pipeline orchestration
- **ICAR** (Indian Council of Agricultural Research) – Domain knowledge
- **Ministry of Agriculture, GOI** – Scheme information and MSP data
- **Bootstrap 5** – Responsive UI framework

---

<div align="center">
  <p><strong>🌾 AgriGenie AI – Empowering Indian Farmers with Artificial Intelligence</strong></p>
  <p><em>Jai Jawan, Jai Kisan, Jai Vigyan!</em> 🇮🇳</p>
  <p>Made with ❤️ for 140 million Indian farmer families</p>
</div>
