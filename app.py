"""
AgriGenie AI – Smart Farming Advice Agent
==========================================
Main Flask Application
"""

import os
import json
import logging
import hashlib
import threading
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ── Load environment ──────────────────────────────────────
load_dotenv()

# ── Flask ─────────────────────────────────────────────────
from typing import Optional
from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for, flash, send_file, abort)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user,
                          login_required, logout_user, current_user)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ── RAG pipeline ──────────────────────────────────────────
from rag_pipeline import rag_manager

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("agrigenie")

# ══════════════════════════════════════════════════════════
#  AGENT INSTRUCTIONS
#  ─────────────────────────────────────────────────────────
#  Customise the agent's behavior, tone, and specialisation
#  here.  These instructions are prepended to every prompt.
# ══════════════════════════════════════════════════════════
AGENT_INSTRUCTIONS = """
You are AgriGenie, an expert AI farming advisor specialised in Indian agriculture.

PERSONA & TONE:
- Speak in a friendly, helpful, and encouraging manner like a trusted local agronomist.
- Use simple, clear language that farmers of all education levels can understand.
- When relevant, provide responses in both English and Hindi (use "// Hindi:" marker).
- Address farmers respectfully; use "Kisaan" or "Farmer ji" occasionally.

SPECIALISATION:
- Deep expertise in Indian crop cultivation: Kharif, Rabi, and Zaid seasons.
- Knowledge of Indian states' agro-climatic zones and local crop varieties.
- Familiarity with government schemes: PM-KISAN, PMFBY, Soil Health Card, e-NAM.
- Understanding of Indian mandi price system, APMC, and MSP policies.
- Expertise in Integrated Pest Management (IPM) suitable for Indian conditions.
- Knowledge of organic farming, biofertilizers, and traditional farming wisdom.

RESPONSE STYLE:
- Structure answers with clear headings and bullet points.
- Include specific actionable recommendations (quantities, timings, varieties).
- Mention cost-effective solutions appropriate for small and marginal farmers.
- Always cite government resources, helplines, or schemes when relevant.
- For crop recommendations, always ask about: location/state, soil type, season,
  water availability, and farm size if not provided.
- Keep responses concise but complete (300–500 words for general advice).

SAFETY RULES:
- Always recommend PPE when advising on pesticide use.
- Include pre-harvest intervals (PHI) when recommending pesticides.
- Warn against burning crop residue (environmental and legal implications).
- Discourage over-fertilization; promote soil health.
- For serious plant disease or pest outbreaks, recommend consulting local
  agricultural extension officer (KVK – Krishi Vigyan Kendra).
- Do not provide medical advice; direct human health questions to doctors.
- Do not recommend illegal or banned pesticides (refer to latest CIB&RC list).

MULTILINGUAL SUPPORT:
- Respond in the same language the farmer uses (Hindi, Kannada, Tamil,
  Telugu, Marathi, Gujarati, Punjabi, Bengali, etc.) when detected.
- For technical terms, provide both English term and local language equivalent.

FARMING DOMAINS:
1. Crop Advice: variety selection, sowing, cultivation, harvest
2. Soil Health: pH correction, nutrient management, organic matter
3. Fertilizer: dose, timing, application method, organic alternatives
4. Pest & Disease: identification, IPM, biological control, safe chemicals
5. Irrigation: scheduling, water-saving techniques, drip/sprinkler advice
6. Weather: season-wise advisory, climate adaptation, extreme weather response
7. Market & Mandi: price trends, best time to sell, storage advice
8. Government Schemes: eligibility, application process, benefits
9. Farming Calendar: monthly operations, crop scheduling
10. Organic Farming: certification, markets, transition guidance

KNOWLEDGE BASE USAGE:
- Always check retrieved knowledge base context before answering.
- If knowledge base has relevant information, use it and acknowledge it.
- If information is not in knowledge base, use your training knowledge but
  clearly state it is general guidance.
- Prioritise location-specific advice when the farmer's state is known.
"""

# ══════════════════════════════════════════════════════════
#  Flask App Setup
# ══════════════════════════════════════════════════════════
app = Flask(__name__)

# Config
app.config["SECRET_KEY"]              = os.getenv("FLASK_SECRET_KEY", "agrigenie-dev-key-2024")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(os.getcwd(), 'instance', 'agrigenie.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_ENABLED"]        = True
app.config["MAX_CONTENT_LENGTH"]      = 16 * 1024 * 1024  # 16 MB
app.config["UPLOAD_FOLDER"]           = "uploads"
app.config["REPORTS_FOLDER"]          = "reports"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["REPORTS_FOLDER"], exist_ok=True)
os.makedirs("instance", exist_ok=True)

db      = SQLAlchemy(app)
csrf    = CSRFProtect(app)
login   = LoginManager(app)
login.login_view = "login_page"
login.login_message = ""
login.login_message_category = "warning"

@login.unauthorized_handler
def unauthorized():
    if request.path.startswith("/api/"):
        return jsonify({"error": "Unauthorized"}), 401
    return redirect(url_for("login_page"))

# ══════════════════════════════════════════════════════════
#  IBM watsonx.ai Client
# ══════════════════════════════════════════════════════════
IBM_API_KEY    = os.getenv("IBM_API_KEY", "")
IBM_PROJECT_ID = os.getenv("IBM_PROJECT_ID", "")
IBM_URL        = os.getenv("IBM_URL", "https://us-south.ml.cloud.ibm.com")
IBM_MODEL_ID   = os.getenv("IBM_MODEL_ID", "ibm/granite-3-2-8b-instruct")
IBM_MODEL_FALLBACKS = [
    model for model in [
        IBM_MODEL_ID,
        "ibm/granite-3-8b-instruct",
        "ibm/granite-13b-instruct-v2",
        "ibm/granite-3-3-8b-instruct",
    ] if model
]

_iam_token: dict = {"token": None, "expires_at": 0}


def get_local_fallback_response(prompt: str, include_service_notice: bool = True) -> str:
    """Provide a practical on-device farming fallback when IBM watsonx is unavailable."""
    lowered = prompt.lower()
    if any(word in lowered for word in ["pest", "disease", "insect", "fungus", "virus"]):
        advice = (
            "For pest or disease issues, inspect the crop early and note the exact symptoms.\n"
            "- Remove badly affected leaves, plants, or fruit and keep the field clean.\n"
            "- Use safe IPM steps such as neem-based sprays, traps, or biological controls when appropriate.\n"
            "- If the problem is spreading fast, contact your local KVK or agricultural extension officer."
        )
    elif any(word in lowered for word in ["fertilizer", "nutrient", "npk", "soil"]):
        advice = (
            "For fertilizer planning, test the soil first and avoid over-application.\n"
            "- Match nutrient use to the crop stage and local recommendations.\n"
            "- Add organic matter regularly and use balanced nutrition rather than heavy doses."
        )
    elif any(word in lowered for word in ["irrigation", "water", "drought"]):
        advice = (
            "For irrigation decisions, check soil moisture before watering.\n"
            "- Water early in the morning and prefer drip or sprinkler methods where possible.\n"
            "- Mulch the soil to reduce evaporation and protect roots during dry spells."
        )
    elif any(word in lowered for word in ["weather", "rain", "heat", "storm"]):
        advice = (
            "For weather-related decisions, protect young plants from heat or heavy rain.\n"
            "- Adjust irrigation and avoid spraying before expected rain.\n"
            "- Secure seedlings and use shade or wind protection when needed."
        )
    else:
        advice = (
            "For immediate action, inspect the crop closely and note the symptoms carefully.\n"
            "- Share the crop name, location, soil type, and stage of growth for better advice.\n"
            "- Use local agronomy guidance and contact your nearby extension service for severe issues."
        )

    if include_service_notice:
        return f"Local guidance for now:\n\n{advice}"
    return advice


def get_iam_token() -> Optional[str]:
    """Retrieve (and cache) an IBM IAM access token."""
    import time
    if _iam_token["token"] and time.time() < _iam_token["expires_at"] - 60:
        return _iam_token["token"]
    try:
        resp = requests.post(
            "https://iam.cloud.ibm.com/identity/token",
            data={
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": IBM_API_KEY
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        import time
        _iam_token["token"] = data["access_token"]
        _iam_token["expires_at"] = time.time() + data.get("expires_in", 3600)
        return _iam_token["token"]
    except Exception as exc:
        logger.error(f"IAM token error: {exc}")
        return None

def call_watsonx(prompt: str, max_tokens: int = 1024,
                  temperature: float = 0.7) -> str:
    """Call IBM watsonx.ai text generation endpoint."""
    if not IBM_API_KEY or not IBM_PROJECT_ID:
        return ("⚠️ IBM watsonx.ai credentials not configured. "
                "Please update IBM_API_KEY and IBM_PROJECT_ID in your .env file.")
    token = get_iam_token()
    if not token:
        return "⚠️ Unable to authenticate with IBM Cloud. Check your API key."
    last_error = None
    for model_id in IBM_MODEL_FALLBACKS:
        try:
            url = f"{IBM_URL}/ml/v1/text/generation?version=2023-05-29"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
                "Accept":        "application/json"
            }
            body = {
                "model_id":   model_id,
                "project_id": IBM_PROJECT_ID,
                "input":      prompt,
                "parameters": {
                    "decoding_method":   "greedy",
                    "max_new_tokens":     max_tokens,
                    "min_new_tokens":     20,
                    "temperature":        temperature,
                    "top_k":              50,
                    "top_p":              0.95,
                    "repetition_penalty": 1.1,
                    "stop_sequences":     ["<|endoftext|>", "Human:", "Farmer:"]
                }
            }
            resp = requests.post(url, headers=headers, json=body, timeout=60)
            if resp.status_code == 404:
                try:
                    error_payload = resp.json()
                except Exception:
                    error_payload = {}
                error_message = error_payload.get("errors", [{}])[0].get("message", "")
                last_error = error_message or f"Model '{model_id}' was not found."
                logger.warning(f"watsonx model fallback: {model_id} -> {last_error}")
                continue
            resp.raise_for_status()
            data = resp.json()
            generated = data.get("results", [{}])[0].get("generated_text", "").strip()
            return generated if generated else "I couldn't generate a response. Please try again."
        except requests.exceptions.Timeout:
            last_error = "Request timed out."
            continue
        except requests.exceptions.HTTPError as e:
            logger.error(f"watsonx HTTP error: {e.response.status_code} – {e.response.text}")
            last_error = f"API error ({e.response.status_code})."
            if e.response.status_code == 404:
                continue
            break
        except Exception as exc:
            logger.error(f"watsonx call error: {exc}")
            last_error = str(exc)
            break
    fallback = get_local_fallback_response(prompt, include_service_notice=True)
    return fallback


def build_rag_prompt(user_query: str, farmer_profile: dict = None) -> str:
    """Build a full RAG-augmented prompt for the LLM."""
    # 1. Retrieve context from knowledge base
    context = rag_manager.retrieve(user_query, top_k=5)

    # 2. Farmer profile section
    profile_section = ""
    if farmer_profile:
        profile_section = f"""
FARMER PROFILE:
- Name: {farmer_profile.get('name', 'Unknown')}
- Location: {farmer_profile.get('location', 'India')}
- Land Size: {farmer_profile.get('land_size', 'Not specified')} acres
- Primary Crops: {farmer_profile.get('primary_crops', 'Not specified')}
- Soil Type: {farmer_profile.get('soil_type', 'Not specified')}
- Irrigation: {farmer_profile.get('irrigation_type', 'Not specified')}
- Farming Experience: {farmer_profile.get('experience', 'Not specified')} years
"""

    # 3. Context section
    context_section = ""
    if context:
        context_section = f"""
AGRICULTURAL KNOWLEDGE BASE CONTEXT:
{context}
"""

    # 4. Build full prompt
    prompt = f"""{AGENT_INSTRUCTIONS}
{profile_section}
{context_section}

FARMER'S QUESTION: {user_query}

AGRIGENIE RESPONSE:"""

    return prompt


# ══════════════════════════════════════════════════════════
#  Database Models
# ══════════════════════════════════════════════════════════
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    is_active     = db.Column(db.Boolean, default=True)

    profile       = db.relationship("FarmerProfile", backref="user",
                                    uselist=False, cascade="all, delete-orphan")
    chats         = db.relationship("ChatMessage", backref="user",
                                    cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class FarmerProfile(db.Model):
    __tablename__ = "farmer_profiles"
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name            = db.Column(db.String(100))
    phone           = db.Column(db.String(20))
    state           = db.Column(db.String(60))
    district        = db.Column(db.String(60))
    village         = db.Column(db.String(100))
    land_size       = db.Column(db.Float, default=0.0)   # acres
    soil_type       = db.Column(db.String(60))
    irrigation_type = db.Column(db.String(80))
    primary_crops   = db.Column(db.String(200))
    experience      = db.Column(db.Integer, default=0)   # years
    preferred_lang  = db.Column(db.String(20), default="English")
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow,
                                onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "name":            self.name,
            "phone":           self.phone,
            "state":           self.state,
            "district":        self.district,
            "village":         self.village,
            "land_size":       self.land_size,
            "soil_type":       self.soil_type,
            "irrigation_type": self.irrigation_type,
            "primary_crops":   self.primary_crops,
            "experience":      self.experience,
            "preferred_lang":  self.preferred_lang,
            "location":        f"{self.village}, {self.district}, {self.state}"
                               if self.state else "India"
        }


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    session_id = db.Column(db.String(64))
    role       = db.Column(db.String(10))   # "user" | "assistant"
    content    = db.Column(db.Text, nullable=False)
    topic      = db.Column(db.String(80))   # e.g. "crop", "soil", "pest"
    timestamp  = db.Column(db.DateTime, default=datetime.utcnow)
    model_used = db.Column(db.String(80))

    def to_dict(self) -> dict:
        return {
            "id":        self.id,
            "role":      self.role,
            "content":   self.content,
            "topic":     self.topic,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M"),
            "model":     self.model_used
        }


class CropAnalysis(db.Model):
    __tablename__ = "crop_analyses"
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    crop_name    = db.Column(db.String(80))
    season       = db.Column(db.String(20))
    soil_type    = db.Column(db.String(60))
    location     = db.Column(db.String(100))
    land_size    = db.Column(db.Float)
    ai_advice    = db.Column(db.Text)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)


class SoilAnalysis(db.Model):
    __tablename__ = "soil_analyses"
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ph_value      = db.Column(db.Float)
    organic_carbon= db.Column(db.Float)
    nitrogen      = db.Column(db.String(20))  # low/medium/high
    phosphorus    = db.Column(db.String(20))
    potassium     = db.Column(db.String(20))
    zinc          = db.Column(db.String(20))
    sulfur        = db.Column(db.String(20))
    texture       = db.Column(db.String(40))
    ai_advice     = db.Column(db.Text)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)


@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ══════════════════════════════════════════════════════════
#  Weather Helper
# ══════════════════════════════════════════════════════════
OWM_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

def get_weather(location: str = "New Delhi") -> dict:
    """Fetch weather data; return mock data if API key missing."""
    if OWM_API_KEY:
        try:
            url = (f"https://api.openweathermap.org/data/2.5/weather"
                   f"?q={location}&appid={OWM_API_KEY}&units=metric")
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                d = r.json()
                return {
                    "location":    d["name"],
                    "temperature": round(d["main"]["temp"]),
                    "feels_like":  round(d["main"]["feels_like"]),
                    "humidity":    d["main"]["humidity"],
                    "description": d["weather"][0]["description"].title(),
                    "wind_speed":  d["wind"]["speed"],
                    "icon":        d["weather"][0]["icon"],
                    "source":      "live"
                }
        except Exception as exc:
            logger.warning(f"Weather API error: {exc}")

    # Mock weather for demo
    import random
    month = datetime.now().month
    if 3 <= month <= 6:
        temp, hum, desc = random.randint(30, 45), random.randint(20, 50), "Sunny & Hot"
    elif 7 <= month <= 9:
        temp, hum, desc = random.randint(25, 35), random.randint(70, 95), "Partly Cloudy with Rain"
    elif 10 <= month <= 11:
        temp, hum, desc = random.randint(20, 30), random.randint(50, 70), "Pleasant"
    else:
        temp, hum, desc = random.randint(8, 22), random.randint(40, 65), "Cold & Clear"

    return {
        "location":    location,
        "temperature": temp,
        "feels_like":  temp - 2,
        "humidity":    hum,
        "description": desc,
        "wind_speed":  random.randint(5, 25),
        "icon":        "01d",
        "source":      "mock"
    }


# ══════════════════════════════════════════════════════════
#  Mandi Price Helper (mock data with real-looking values)
# ══════════════════════════════════════════════════════════
MOCK_MANDI_PRICES = {
    "Wheat":     {"modal": 2280, "min": 2200, "max": 2400, "unit": "quintal", "trend": "stable"},
    "Rice":      {"modal": 2350, "min": 2200, "max": 2600, "unit": "quintal", "trend": "up"},
    "Maize":     {"modal": 2100, "min": 1950, "max": 2300, "unit": "quintal", "trend": "up"},
    "Soybean":   {"modal": 4950, "min": 4800, "max": 5200, "unit": "quintal", "trend": "stable"},
    "Cotton":    {"modal": 7300, "min": 7100, "max": 7600, "unit": "quintal", "trend": "up"},
    "Sugarcane": {"modal": 350,  "min": 325,  "max": 380,  "unit": "quintal", "trend": "stable"},
    "Onion":     {"modal": 2200, "min": 1800, "max": 3200, "unit": "quintal", "trend": "volatile"},
    "Potato":    {"modal": 850,  "min": 700,  "max": 1100, "unit": "quintal", "trend": "down"},
    "Tomato":    {"modal": 3500, "min": 1500, "max": 7000, "unit": "quintal", "trend": "volatile"},
    "Groundnut": {"modal": 6900, "min": 6600, "max": 7200, "unit": "quintal", "trend": "stable"},
    "Mustard":   {"modal": 5750, "min": 5500, "max": 6000, "unit": "quintal", "trend": "up"},
    "Chickpea":  {"modal": 5600, "min": 5300, "max": 5900, "unit": "quintal", "trend": "stable"},
    "Tur Dal":   {"modal": 7800, "min": 7500, "max": 8200, "unit": "quintal", "trend": "up"},
    "Moong Dal": {"modal": 8900, "min": 8600, "max": 9500, "unit": "quintal", "trend": "up"},
    "Turmeric":  {"modal": 14000,"min": 12000,"max": 16000,"unit": "quintal", "trend": "up"},
    "Chili":     {"modal": 12000,"min": 9000, "max": 16000,"unit": "quintal", "trend": "volatile"},
}

def get_mandi_prices(crops: list = None) -> dict:
    """Return current mandi price data (mock)."""
    if crops:
        return {c: MOCK_MANDI_PRICES[c] for c in crops if c in MOCK_MANDI_PRICES}
    return MOCK_MANDI_PRICES


# ══════════════════════════════════════════════════════════
#  Report Generation
# ══════════════════════════════════════════════════════════
def generate_farming_report(report_type: str, data: dict, user: User) -> str:
    """Generate a PDF farming report; returns file path."""
    try:
        from fpdf import FPDF
        import time

        pdf = FPDF()
        pdf.add_page()

        # Header
        pdf.set_fill_color(34, 139, 34)
        pdf.rect(0, 0, 210, 35, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_xy(10, 8)
        pdf.cell(190, 12, "AgriGenie AI - Smart Farming Report", align="C")
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(10, 22)
        pdf.cell(190, 8, f"Report Type: {report_type}  |  Generated: {datetime.now().strftime('%d %b %Y %H:%M')}", align="C")

        pdf.set_text_color(0, 0, 0)
        pdf.set_y(45)

        # Farmer info
        profile = user.profile
        if profile:
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_fill_color(230, 247, 230)
            pdf.cell(190, 8, "Farmer Information", fill=True, ln=True)
            pdf.set_font("Helvetica", "", 11)
            pdf.ln(2)
            info_pairs = [
                ("Name", profile.name or user.username),
                ("Location", f"{profile.village or ''}, {profile.district or ''}, {profile.state or ''}"),
                ("Land Size", f"{profile.land_size or 0} Acres"),
                ("Primary Crops", profile.primary_crops or "Not specified"),
                ("Soil Type", profile.soil_type or "Not specified"),
                ("Irrigation", profile.irrigation_type or "Not specified"),
            ]
            for k, v in info_pairs:
                pdf.cell(60, 7, f"  {k}:", border=0)
                pdf.cell(130, 7, str(v), border=0, ln=True)
            pdf.ln(5)

        # AI Advice content
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_fill_color(230, 247, 230)
        pdf.cell(190, 8, f"{report_type} Analysis & Recommendations", fill=True, ln=True)
        pdf.ln(3)
        pdf.set_font("Helvetica", "", 10)

        advice = data.get("advice", "No advice generated.")
        # Clean text for PDF
        advice_clean = advice.encode("latin-1", errors="replace").decode("latin-1")
        lines = advice_clean.split("\n")
        for line in lines:
            if line.strip().startswith("##"):
                pdf.set_font("Helvetica", "B", 11)
                pdf.ln(3)
                pdf.cell(190, 6, line.replace("#", "").strip(), ln=True)
                pdf.set_font("Helvetica", "", 10)
            elif line.strip().startswith("-") or line.strip().startswith("*"):
                pdf.cell(10, 5, "")
                pdf.multi_cell(180, 5, line.strip("- *"))
            elif line.strip():
                pdf.multi_cell(190, 5, line.strip())
            else:
                pdf.ln(2)

        # Footer
        pdf.set_y(-20)
        pdf.set_fill_color(34, 139, 34)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(190, 10,
                 "AgriGenie AI | Powered by IBM watsonx.ai Granite | "
                 "For Guidance Only – Consult Local KVK for Field-Specific Advice",
                 align="C")

        filename = f"report_{report_type.lower().replace(' ', '_')}_{int(time.time())}.pdf"
        filepath = os.path.join(app.config["REPORTS_FOLDER"], filename)
        pdf.output(filepath)
        return filepath

    except Exception as exc:
        logger.error(f"Report generation error: {exc}")
        return None


# ══════════════════════════════════════════════════════════
#  Routes – Auth
# ══════════════════════════════════════════════════════════
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        data = request.get_json() or request.form
        username = data.get("username", "").strip()
        password = data.get("password", "")
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            session.pop('_flashes', None)
            if request.is_json:
                return jsonify({"success": True, "redirect": url_for("dashboard")})
            return redirect(url_for("dashboard"))
        if request.is_json:
            return jsonify({"success": False, "message": "Invalid username or password"}), 401
        flash("Invalid username or password", "danger")
    return render_template("auth.html", page="login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = request.get_json() or request.form
        username = data.get("username", "").strip()
        email    = data.get("email", "").strip()
        password = data.get("password", "")

        if not username or not email or not password:
            if request.is_json:
                return jsonify({"success": False, "message": "All fields required"}), 400
            flash("All fields required", "danger")
            return render_template("auth.html", page="register")

        if User.query.filter_by(username=username).first():
            if request.is_json:
                return jsonify({"success": False, "message": "Username already taken"}), 400
            flash("Username already taken", "danger")
            return render_template("auth.html", page="register")

        if User.query.filter_by(email=email).first():
            if request.is_json:
                return jsonify({"success": False, "message": "Email already registered"}), 400
            flash("Email already registered", "danger")
            return render_template("auth.html", page="register")

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        profile = FarmerProfile(user_id=user.id, name=username)
        db.session.add(profile)
        db.session.commit()

        login_user(user, remember=True)
        if request.is_json:
            return jsonify({"success": True, "redirect": url_for("dashboard")})
        return redirect(url_for("profile_page"))

    return render_template("auth.html", page="register")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# ══════════════════════════════════════════════════════════
#  Routes – Dashboard & Pages
# ══════════════════════════════════════════════════════════
@app.route("/dashboard")
@login_required
def dashboard():
    profile = current_user.profile
    weather = get_weather(
        profile.state or os.getenv("DEFAULT_LOCATION", "New Delhi")
        if profile else os.getenv("DEFAULT_LOCATION", "New Delhi")
    )
    chat_count = ChatMessage.query.filter_by(
        user_id=current_user.id, role="user").count()
    recent_chats = ChatMessage.query.filter_by(
        user_id=current_user.id
    ).order_by(ChatMessage.timestamp.desc()).limit(5).all()
    prices = get_mandi_prices(["Wheat", "Rice", "Maize", "Soybean",
                                "Cotton", "Onion", "Potato", "Tomato"])
    month_name = datetime.now().strftime("%B")
    return render_template("dashboard.html",
                           profile=profile,
                           weather=weather,
                           chat_count=chat_count,
                           recent_chats=recent_chats,
                           prices=prices,
                           month=month_name)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile_page():
    profile = current_user.profile
    if not profile:
        profile = FarmerProfile(user_id=current_user.id)
        db.session.add(profile)

    if request.method == "POST":
        data = request.get_json() or request.form
        fields = ["name","phone","state","district","village","soil_type",
                  "irrigation_type","primary_crops","preferred_lang"]
        for f in fields:
            if f in data:
                setattr(profile, f, data[f])
        try:
            profile.land_size  = float(data.get("land_size", 0))
            profile.experience = int(data.get("experience", 0))
        except (ValueError, TypeError):
            pass
        profile.updated_at = datetime.utcnow()
        db.session.commit()
        if request.is_json:
            return jsonify({"success": True, "message": "Profile updated successfully!"})
        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile_page"))

    return render_template("profile.html", profile=profile, user=current_user)


@app.route("/chat")
@login_required
def chat_page():
    history = ChatMessage.query.filter_by(
        user_id=current_user.id
    ).order_by(ChatMessage.timestamp.desc()).limit(50).all()
    profile = current_user.profile
    return render_template("chat.html", history=history, profile=profile)


@app.route("/crop-advisor")
@login_required
def crop_advisor():
    return render_template("crop_advisor.html", profile=current_user.profile)


@app.route("/soil-health")
@login_required
def soil_health():
    analyses = SoilAnalysis.query.filter_by(
        user_id=current_user.id
    ).order_by(SoilAnalysis.created_at.desc()).limit(10).all()
    return render_template("soil_health.html",
                           profile=current_user.profile,
                           analyses=analyses)


@app.route("/weather")
@login_required
def weather_page():
    profile = current_user.profile
    location = profile.state if profile and profile.state else "New Delhi"
    weather  = get_weather(location)
    return render_template("weather.html", weather=weather, profile=profile)


@app.route("/fertilizer")
@login_required
def fertilizer_page():
    return render_template("fertilizer.html", profile=current_user.profile)


@app.route("/pest-advisor")
@login_required
def pest_advisor():
    return render_template("pest_advisor.html", profile=current_user.profile)


@app.route("/irrigation")
@login_required
def irrigation_page():
    return render_template("irrigation.html", profile=current_user.profile)


@app.route("/mandi-prices")
@login_required
def mandi_prices():
    prices = get_mandi_prices()
    return render_template("mandi_prices.html",
                           prices=prices,
                           profile=current_user.profile)


@app.route("/government-schemes")
@login_required
def govt_schemes():
    return render_template("govt_schemes.html", profile=current_user.profile)


@app.route("/farming-calendar")
@login_required
def farming_calendar():
    month = datetime.now().month
    return render_template("farming_calendar.html",
                           current_month=month,
                           profile=current_user.profile)


@app.route("/chat-history")
@login_required
def chat_history():
    page = request.args.get("page", 1, type=int)
    topic_filter = request.args.get("topic", "")
    query = ChatMessage.query.filter_by(
        user_id=current_user.id, role="user"
    )
    if topic_filter:
        query = query.filter_by(topic=topic_filter)
    messages = query.order_by(
        ChatMessage.timestamp.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    return render_template("chat_history.html",
                           messages=messages,
                           topic_filter=topic_filter)


# ══════════════════════════════════════════════════════════
#  API Routes – AI Chat & Advisories
# ══════════════════════════════════════════════════════════
@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data     = request.get_json()
    message  = (data.get("message") or "").strip()
    topic    = data.get("topic", "general")
    sess_id  = data.get("session_id", "")

    if not message:
        return jsonify({"error": "Message cannot be empty"}), 400

    # Build profile context
    profile_dict = current_user.profile.to_dict() if current_user.profile else {}

    # Build prompt with RAG context
    prompt = build_rag_prompt(message, profile_dict)

    # Call watsonx
    response = call_watsonx(prompt, max_tokens=1024)

    # Save chat messages
    user_msg = ChatMessage(
        user_id=current_user.id,
        session_id=sess_id,
        role="user",
        content=message,
        topic=topic,
        model_used=IBM_MODEL_ID
    )
    ai_msg = ChatMessage(
        user_id=current_user.id,
        session_id=sess_id,
        role="assistant",
        content=response,
        topic=topic,
        model_used=IBM_MODEL_ID
    )
    db.session.add_all([user_msg, ai_msg])
    db.session.commit()

    return jsonify({
        "response":   response,
        "message_id": ai_msg.id,
        "timestamp":  ai_msg.timestamp.strftime("%Y-%m-%d %H:%M"),
        "model":      IBM_MODEL_ID
    })


@app.route("/api/crop-recommendation", methods=["POST"])
@login_required
def api_crop_recommendation():
    data = request.get_json()
    fields = {
        "location":   data.get("location", "India"),
        "soil_type":  data.get("soil_type", "loamy"),
        "season":     data.get("season", "Kharif"),
        "water":      data.get("water_availability", "moderate"),
        "land_size":  data.get("land_size", "1"),
        "budget":     data.get("budget", "moderate"),
        "prev_crop":  data.get("previous_crop", "none"),
    }
    query = (f"Recommend the best crops for a farmer in {fields['location']} "
             f"with {fields['soil_type']} soil during {fields['season']} season. "
             f"Water availability: {fields['water']}. "
             f"Farm size: {fields['land_size']} acres. "
             f"Budget: {fields['budget']}. "
             f"Previous crop: {fields['prev_crop']}. "
             f"Give top 3 crop recommendations with full cultivation guide, "
             f"expected yield, and profit potential.")
    profile_dict = current_user.profile.to_dict() if current_user.profile else {}
    prompt   = build_rag_prompt(query, profile_dict)
    advice   = call_watsonx(prompt, max_tokens=1200)

    # Save analysis
    analysis = CropAnalysis(
        user_id  = current_user.id,
        crop_name= data.get("crop_interest", "Multiple"),
        season   = fields["season"],
        soil_type= fields["soil_type"],
        location = fields["location"],
        land_size= float(fields["land_size"] or 0),
        ai_advice= advice
    )
    db.session.add(analysis)
    db.session.commit()

    return jsonify({"advice": advice, "analysis_id": analysis.id})


@app.route("/api/soil-analysis", methods=["POST"])
@login_required
def api_soil_analysis():
    data = request.get_json()
    ph  = data.get("ph", 7.0)
    oc  = data.get("organic_carbon", 0.5)
    n   = data.get("nitrogen", "medium")
    p   = data.get("phosphorus", "medium")
    k   = data.get("potassium", "medium")
    zn  = data.get("zinc", "sufficient")
    s   = data.get("sulfur", "sufficient")
    tex = data.get("texture", "loamy")
    crop= data.get("crop", "wheat")

    query = (f"Soil analysis results: pH={ph}, Organic Carbon={oc}%, "
             f"Nitrogen={n}, Phosphorus={p}, Potassium={k}, "
             f"Zinc={zn}, Sulfur={s}, Texture={tex}. "
             f"Planned crop: {crop}. "
             f"Provide: 1) Soil health interpretation, "
             f"2) Specific amendments needed with doses, "
             f"3) Fertilizer schedule for the planned crop, "
             f"4) Long-term soil improvement plan.")
    profile_dict = current_user.profile.to_dict() if current_user.profile else {}
    prompt = build_rag_prompt(query, profile_dict)
    advice = call_watsonx(prompt, max_tokens=1200)

    # Save
    analysis = SoilAnalysis(
        user_id       = current_user.id,
        ph_value      = float(ph),
        organic_carbon= float(oc),
        nitrogen      = n,
        phosphorus    = p,
        potassium     = k,
        zinc          = zn,
        sulfur        = s,
        texture       = tex,
        ai_advice     = advice
    )
    db.session.add(analysis)
    db.session.commit()

    return jsonify({"advice": advice, "analysis_id": analysis.id})


@app.route("/api/weather-advisory", methods=["POST"])
@login_required
def api_weather_advisory():
    data     = request.get_json()
    location = data.get("location", "India")
    crop     = data.get("crop", "")
    weather  = get_weather(location)

    query = (f"Current weather in {location}: {weather['description']}, "
             f"Temperature: {weather['temperature']}°C, "
             f"Humidity: {weather['humidity']}%, "
             f"Wind: {weather['wind_speed']} km/h. "
             f"Crop growing: {crop or 'general farming'}. "
             f"Provide weather-based farming advisory including: "
             f"1) Suitable farming operations today, "
             f"2) Pest/disease risk based on weather, "
             f"3) Irrigation adjustment, "
             f"4) Next 7-day farming action plan.")
    profile_dict = current_user.profile.to_dict() if current_user.profile else {}
    prompt = build_rag_prompt(query, profile_dict)
    advice = call_watsonx(prompt, max_tokens=1000)

    return jsonify({"advice": advice, "weather": weather})


@app.route("/api/fertilizer-recommendation", methods=["POST"])
@login_required
def api_fertilizer_recommendation():
    data     = request.get_json()
    crop     = data.get("crop", "wheat")
    area     = data.get("area", 1)
    stage    = data.get("growth_stage", "sowing")
    soil_ph  = data.get("soil_ph", 7.0)
    soil_oc  = data.get("organic_carbon", 0.5)
    irrig    = data.get("irrigation", "irrigated")
    organic  = data.get("prefer_organic", False)

    pref = "organic / natural alternatives preferred, " if organic else ""
    query = (f"Fertilizer recommendation for {crop} crop: "
             f"Area={area} acres, Growth stage={stage}, "
             f"Soil pH={soil_ph}, Organic Carbon={soil_oc}%, "
             f"Irrigation={irrig}. {pref}"
             f"Provide: 1) Complete NPK schedule with doses in kg/acre, "
             f"2) Micronutrient recommendations, "
             f"3) Application timing and method, "
             f"4) Organic alternatives if applicable, "
             f"5) Total fertilizer cost estimate.")
    profile_dict = current_user.profile.to_dict() if current_user.profile else {}
    prompt = build_rag_prompt(query, profile_dict)
    advice = call_watsonx(prompt, max_tokens=1200)

    return jsonify({"advice": advice})


@app.route("/api/pest-diagnosis", methods=["POST"])
@login_required
def api_pest_diagnosis():
    data     = request.get_json()
    crop     = data.get("crop", "")
    symptoms = data.get("symptoms", "")
    stage    = data.get("crop_stage", "")
    location = data.get("location", "India")
    severity = data.get("severity", "moderate")

    query = (f"Pest/disease diagnosis for {crop} crop in {location}. "
             f"Growth stage: {stage}. Severity: {severity}. "
             f"Observed symptoms: {symptoms}. "
             f"Provide: 1) Most likely pest/disease identification, "
             f"2) Confirmation field tests, "
             f"3) IPM-based management (biological first, then chemical), "
             f"4) Specific pesticide/fungicide names with doses, "
             f"5) Pre-harvest interval, "
             f"6) Prevention for next season.")
    profile_dict = current_user.profile.to_dict() if current_user.profile else {}
    prompt = build_rag_prompt(query, profile_dict)
    advice = call_watsonx(prompt, max_tokens=1200)

    return jsonify({"advice": advice})


@app.route("/api/irrigation-plan", methods=["POST"])
@login_required
def api_irrigation_plan():
    data    = request.get_json()
    crop    = data.get("crop", "wheat")
    area    = data.get("area", 1)
    method  = data.get("current_method", "flood")
    soil    = data.get("soil_type", "loamy")
    season  = data.get("season", "Rabi")
    water   = data.get("water_source", "borewell")

    query = (f"Irrigation plan for {crop}: Area={area} acres, "
             f"Current method={method}, Soil={soil}, "
             f"Season={season}, Water source={water}. "
             f"Provide: 1) Stage-wise irrigation schedule with intervals, "
             f"2) Total water requirement, "
             f"3) Water saving tips for this crop, "
             f"4) Should they switch to drip/sprinkler? Cost-benefit, "
             f"5) Critical irrigation stages warning, "
             f"6) Government subsidy available for irrigation improvement.")
    profile_dict = current_user.profile.to_dict() if current_user.profile else {}
    prompt = build_rag_prompt(query, profile_dict)
    advice = call_watsonx(prompt, max_tokens=1200)

    return jsonify({"advice": advice})


@app.route("/api/mandi-analysis", methods=["POST"])
@login_required
def api_mandi_analysis():
    data  = request.get_json()
    crop  = data.get("crop", "Wheat")
    qty   = data.get("quantity", 10)
    state = data.get("state", "")

    prices = get_mandi_prices([crop])
    price_info = prices.get(crop, {})

    query = (f"Market analysis for {crop}: "
             f"Current modal price ₹{price_info.get('modal', 'N/A')}/quintal, "
             f"Min: ₹{price_info.get('min', 'N/A')}, Max: ₹{price_info.get('max', 'N/A')}, "
             f"Trend: {price_info.get('trend', 'stable')}. "
             f"Farmer has {qty} quintals to sell. Location: {state or 'India'}. "
             f"Provide: 1) Should farmer sell now or wait? "
             f"2) Best mandis/markets for this crop, "
             f"3) Storage options and cost-benefit of waiting, "
             f"4) How to get MSP if market price is low, "
             f"5) Export opportunities if any.")
    profile_dict = current_user.profile.to_dict() if current_user.profile else {}
    prompt = build_rag_prompt(query, profile_dict)
    advice = call_watsonx(prompt, max_tokens=1000)

    return jsonify({"advice": advice, "price_data": price_info})


@app.route("/api/scheme-eligibility", methods=["POST"])
@login_required
def api_scheme_eligibility():
    data    = request.get_json()
    scheme  = data.get("scheme", "PM-KISAN")
    profile = current_user.profile

    query = (f"Explain the {scheme} government scheme in detail: "
             f"eligibility, benefits, application process, and documents required. "
             f"Farmer details: "
             f"State: {profile.state if profile else 'India'}, "
             f"Land: {profile.land_size if profile else 1} acres, "
             f"Crops: {profile.primary_crops if profile else 'mixed'}. "
             f"Is this farmer eligible? Step-by-step application guide.")
    profile_dict = profile.to_dict() if profile else {}
    prompt = build_rag_prompt(query, profile_dict)
    advice = call_watsonx(prompt, max_tokens=1000)

    return jsonify({"advice": advice})


@app.route("/api/calendar-advisory", methods=["POST"])
@login_required
def api_calendar_advisory():
    data  = request.get_json()
    month = data.get("month", datetime.now().month)
    crop  = data.get("crop", "")
    state = data.get("state", "")

    month_name = datetime(2024, month, 1).strftime("%B")
    query = (f"Farming operations advisory for {month_name} month "
             f"in {state or 'North India'}. "
             f"Focus crop: {crop or 'all major crops'}. "
             f"Provide: 1) Key farming activities to do this month, "
             f"2) Sowing/transplanting/harvest schedule, "
             f"3) Fertilizer and irrigation schedule, "
             f"4) Pest/disease watch list for this month, "
             f"5) Market opportunities this month.")
    profile_dict = current_user.profile.to_dict() if current_user.profile else {}
    prompt = build_rag_prompt(query, profile_dict)
    advice = call_watsonx(prompt, max_tokens=1100)

    return jsonify({"advice": advice, "month": month_name})


# ══════════════════════════════════════════════════════════
#  API Routes – Utility
# ══════════════════════════════════════════════════════════
@app.route("/api/weather", methods=["GET"])
@login_required
def api_weather():
    location = request.args.get("location", "New Delhi")
    return jsonify(get_weather(location))


@app.route("/api/mandi-prices", methods=["GET"])
@login_required
def api_mandi_prices():
    return jsonify(get_mandi_prices())


@app.route("/api/chat-history", methods=["GET"])
@login_required
def api_chat_history():
    limit = request.args.get("limit", 20, type=int)
    messages = ChatMessage.query.filter_by(
        user_id=current_user.id
    ).order_by(ChatMessage.timestamp.desc()).limit(limit).all()
    return jsonify([m.to_dict() for m in reversed(messages)])


@app.route("/api/chat-history/<int:msg_id>", methods=["DELETE"])
@login_required
def api_delete_chat(msg_id):
    msg = ChatMessage.query.filter_by(
        id=msg_id, user_id=current_user.id
    ).first_or_404()
    db.session.delete(msg)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/chat-history/clear", methods=["DELETE"])
@login_required
def api_clear_chat():
    ChatMessage.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"success": True, "message": "Chat history cleared"})


@app.route("/api/download-report", methods=["POST"])
@login_required
def api_download_report():
    data        = request.get_json()
    report_type = data.get("report_type", "Farming Advisory")
    advice      = data.get("advice", "")

    filepath = generate_farming_report(
        report_type,
        {"advice": advice},
        current_user
    )
    if not filepath or not os.path.exists(filepath):
        return jsonify({"error": "Report generation failed"}), 500

    return send_file(
        filepath,
        as_attachment=True,
        download_name=os.path.basename(filepath),
        mimetype="application/pdf"
    )


@app.route("/api/rag-status", methods=["GET"])
def api_rag_status():
    return jsonify({
        "ready":   rag_manager.is_ready,
        "backend": os.getenv("VECTOR_STORE", "faiss")
    })


@app.route("/api/rag-rebuild", methods=["POST"])
@login_required
def api_rag_rebuild():
    try:
        rag_manager.rebuild()
        return jsonify({"success": True, "message": "Knowledge base index rebuilt"})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ══════════════════════════════════════════════════════════
#  Error Handlers
# ══════════════════════════════════════════════════════════
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return render_template("error.html", code=404, message="Page not found"), 404


@app.errorhandler(500)
def server_error(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error"}), 500
    return render_template("error.html", code=500, message="Internal server error"), 500


# ══════════════════════════════════════════════════════════
#  Application Startup
# ══════════════════════════════════════════════════════════
def start_rag_initialization():
    try:
        rag_manager.initialize()
    except Exception as exc:
        logger.warning(f"RAG initialisation deferred: {exc}")


def create_app():
    with app.app_context():
        db.create_all()
        logger.info("Database tables created")

        try:
            threading.Thread(
                target=start_rag_initialization,
                name="rag-init",
                daemon=True,
            ).start()
        except Exception as exc:
            logger.warning(f"RAG background startup failed: {exc}")

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    logger.info(f"🌱 AgriGenie AI starting on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
