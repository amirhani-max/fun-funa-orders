import os
import smtplib
import sqlite3
import uuid
import re
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
import uvicorn

load_dotenv()

app = FastAPI(
    title="Fun Fana Order System",
    docs_url=None,          # Hide /docs in production
    redoc_url=None,         # Hide /redoc
    openapi_url=None,       # Hide OpenAPI schema
)

# Paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = BASE_DIR / "uploads"
TEMPLATES_DIR = BASE_DIR / "templates"

STATIC_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

DB_PATH = BASE_DIR / "orders.db"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ==================== SECURITY ====================
# Simple rate limiting (in-memory)
from collections import defaultdict
import time

request_counts = defaultdict(list)
RATE_LIMIT = 10          # max requests
RATE_WINDOW = 60         # per 60 seconds

class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"

        # Rate limiting
        now = time.time()
        request_counts[client_ip] = [t for t in request_counts[client_ip] if now - t < RATE_WINDOW]
        if len(request_counts[client_ip]) >= RATE_LIMIT:
            return JSONResponse(status_code=429, content={"detail": "Too many requests. Please wait a minute."})
        request_counts[client_ip].append(now)

        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:;"
        return response

app.add_middleware(SecurityMiddleware)

# Allow only same origin by default (can be adjusted)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your domain later for more security
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ==================== CONFIG ====================
PRICE_PER_ITEM = 50
INSTAPAY_NUMBER = "01274444082"
BUSINESS_EMAIL = "fun.funa.eg@gmail.com"
BUSINESS_NAME = "Fun Fana"
ESTIMATED_DAYS = "4–5 working days"
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "fun.funa.eg@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

COLORS = [
    {"name": "Neon Pink", "hex": "#FF10F0"},
    {"name": "Light Pink", "hex": "#FFB6C1"},
    {"name": "Pink", "hex": "#FFC0CB"},
    {"name": "Lilac", "hex": "#C8A2C8"},
    {"name": "Purple", "hex": "#800080"},
    {"name": "Oil Green", "hex": "#3B5E2B"},
    {"name": "Olive Green", "hex": "#6B8E23"},
    {"name": "Light Turquoise", "hex": "#AFEEEE"},
    {"name": "Light Blue", "hex": "#ADD8E6"},
    {"name": "Sky Blue", "hex": "#87CEEB"},
    {"name": "Black", "hex": "#000000"},
    {"name": "Red", "hex": "#FF0000"},
    {"name": "Green", "hex": "#008000"},
    {"name": "Peak Green", "hex": "#00FF7F"},
    {"name": "Orange", "hex": "#FFA500"},
    {"name": "White", "hex": "#FFFFFF"},
]

ALLOWED_COLORS = {c["name"] for c in COLORS}


# ==================== HELPERS ====================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            keychain_name TEXT NOT NULL,
            color TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            total INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            screenshot_path TEXT,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            ip_address TEXT
        )
    """)
    conn.commit()
    conn.close()


def generate_order_number() -> str:
    now = datetime.now()
    date_part = now.strftime("%Y%m%d")
    unique = str(uuid.uuid4())[:4].upper()
    return f"FF-{date_part}-{unique}"


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def is_valid_phone(phone: str) -> bool:
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    return bool(re.match(r"^01[0125]\d{8}$", cleaned)) or bool(re.match(r"^\+?20\d{10}$", cleaned))


def save_order(data: dict) -> str:
    order_number = generate_order_number()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO orders (
            order_number, customer_name, customer_phone, customer_email,
            keychain_name, color, quantity, total, payment_method,
            screenshot_path, created_at, ip_address
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_number,
        data["customer_name"],
        data["customer_phone"],
        data["customer_email"],
        data["keychain_name"],
        data["color"],
        data["quantity"],
        data["total"],
        data["payment_method"],
        data.get("screenshot_path"),
        data["created_at"],
        data.get("ip_address"),
    ))
    conn.commit()
    conn.close()
    return order_number


def send_order_email(order_data: dict, screenshot_path: Optional[str] = None) -> bool:
    if not SENDER_PASSWORD:
        print("WARNING: SENDER_PASSWORD not set. Email not sent.")
        return False

    try:
        msg = MIMEMultipart("related")
        msg["Subject"] = f"New Order #{order_data['order_number']} – {BUSINESS_NAME}"
        msg["From"] = f"{BUSINESS_NAME} <{SENDER_EMAIL}>"
        msg["To"] = BUSINESS_EMAIL

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 24px; text-align: center; border-radius: 12px 12px 0 0;">
                <h1 style="margin: 0; font-size: 28px;">{BUSINESS_NAME}</h1>
                <p style="margin: 8px 0 0; opacity: 0.9;">New Keychain Order</p>
            </div>
            
            <div style="background: #f8f9fa; padding: 24px; border: 1px solid #e9ecef;">
                <h2 style="color: #667eea; margin-top: 0;">Order Details</h2>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 8px 0; font-weight: bold; width: 40%;">Order Number:</td>
                        <td style="padding: 8px 0;">{order_data['order_number']}</td></tr>
                    <tr><td style="padding: 8px 0; font-weight: bold;">Date & Time:</td>
                        <td style="padding: 8px 0;">{order_data['created_at']}</td></tr>
                    <tr><td style="padding: 8px 0; font-weight: bold;">Estimated Ready:</td>
                        <td style="padding: 8px 0;">{ESTIMATED_DAYS}</td></tr>
                </table>
                
                <hr style="border: none; border-top: 1px solid #dee2e6; margin: 20px 0;">
                
                <h3 style="color: #495057;">Customer Information</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 6px 0; font-weight: bold; width: 40%;">Name:</td>
                        <td style="padding: 6px 0;">{order_data['customer_name']}</td></tr>
                    <tr><td style="padding: 6px 0; font-weight: bold;">Phone:</td>
                        <td style="padding: 6px 0;">{order_data['customer_phone']}</td></tr>
                    <tr><td style="padding: 6px 0; font-weight: bold;">Email:</td>
                        <td style="padding: 6px 0;">{order_data['customer_email']}</td></tr>
                </table>
                
                <hr style="border: none; border-top: 1px solid #dee2e6; margin: 20px 0;">
                
                <h3 style="color: #495057;">Product</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 6px 0; font-weight: bold; width: 40%;">Item:</td>
                        <td style="padding: 6px 0;">Custom Name Keychain</td></tr>
                    <tr><td style="padding: 6px 0; font-weight: bold;">Name on Keychain:</td>
                        <td style="padding: 6px 0; font-size: 18px; color: #667eea;"><strong>{order_data['keychain_name']}</strong></td></tr>
                    <tr><td style="padding: 6px 0; font-weight: bold;">Color:</td>
                        <td style="padding: 6px 0;">{order_data['color']}</td></tr>
                    <tr><td style="padding: 6px 0; font-weight: bold;">Quantity:</td>
                        <td style="padding: 6px 0;">{order_data['quantity']}</td></tr>
                    <tr><td style="padding: 6px 0; font-weight: bold;">Price per item:</td>
                        <td style="padding: 6px 0;">{PRICE_PER_ITEM} EGP</td></tr>
                    <tr><td style="padding: 6px 0; font-weight: bold; font-size: 16px;">Total:</td>
                        <td style="padding: 6px 0; font-size: 18px; color: #28a745;"><strong>{order_data['total']} EGP</strong></td></tr>
                </table>
                
                <hr style="border: none; border-top: 1px solid #dee2e6; margin: 20px 0;">
                
                <h3 style="color: #495057;">Payment</h3>
                <p style="margin: 0;"><strong>Method:</strong> {order_data['payment_method']}</p>
                {"<p style='margin: 8px 0 0;'><strong>Instapay Number:</strong> " + INSTAPAY_NUMBER + "</p>" if order_data['payment_method'] == "Instapay" else ""}
                {"<p style='margin: 8px 0 0; color: #28a745;'>✓ Payment screenshot attached</p>" if screenshot_path else ""}
            </div>
            
            <div style="background: #343a40; color: #adb5bd; padding: 16px; text-align: center; font-size: 13px; border-radius: 0 0 12px 12px;">
                Automated order from {BUSINESS_NAME} self-service system.
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(html, "html"))

        if screenshot_path and os.path.isfile(screenshot_path):
            with open(screenshot_path, "rb") as f:
                img_data = f.read()
            image = MIMEImage(img_data)
            image.add_header("Content-Disposition", "attachment", filename=os.path.basename(screenshot_path))
            msg.attach(image)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        print(f"Email sent for order {order_data['order_number']}")
        return True

    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


# ==================== ROUTES ====================
@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "colors": COLORS,
        "price": PRICE_PER_ITEM,
        "instapay_number": INSTAPAY_NUMBER,
        "business_name": BUSINESS_NAME,
        "estimated_days": ESTIMATED_DAYS,
    })


@app.post("/api/order")
async def create_order(
    request: Request,
    customer_name: str = Form(...),
    customer_phone: str = Form(...),
    customer_email: str = Form(...),
    keychain_name: str = Form(...),
    color: str = Form(...),
    quantity: int = Form(...),
    payment_method: str = Form(...),
    screenshot: Optional[UploadFile] = File(None),
):
    # --- Validation ---
    customer_name = customer_name.strip()
    customer_phone = customer_phone.strip()
    customer_email = customer_email.strip().lower()
    keychain_name = keychain_name.strip()

    if not customer_name or len(customer_name) > 80:
        raise HTTPException(status_code=400, detail="Invalid name")
    if not is_valid_phone(customer_phone):
        raise HTTPException(status_code=400, detail="Invalid Egyptian phone number")
    if not is_valid_email(customer_email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    if not keychain_name or len(keychain_name) > 20:
        raise HTTPException(status_code=400, detail="Keychain name must be 1-20 characters")
    if color not in ALLOWED_COLORS:
        raise HTTPException(status_code=400, detail="Invalid color")
    if quantity < 1 or quantity > 50:
        raise HTTPException(status_code=400, detail="Quantity must be between 1 and 50")
    if payment_method not in ["Cash", "Instapay"]:
        raise HTTPException(status_code=400, detail="Invalid payment method")

    total = quantity * PRICE_PER_ITEM
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    client_ip = request.client.host if request.client else None

    # --- Handle screenshot ---
    screenshot_path = None
    if screenshot and screenshot.filename:
        content = await screenshot.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400, detail="Image too large (max 5MB)")
        ext = Path(screenshot.filename).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            raise HTTPException(status_code=400, detail="Only JPG, PNG or WEBP allowed")
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = UPLOAD_DIR / filename
        with open(filepath, "wb") as f:
            f.write(content)
        screenshot_path = str(filepath)

    order_data = {
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "customer_email": customer_email,
        "keychain_name": keychain_name,
        "color": color,
        "quantity": quantity,
        "total": total,
        "payment_method": payment_method,
        "screenshot_path": screenshot_path,
        "created_at": created_at,
        "ip_address": client_ip,
    }

    order_number = save_order(order_data)
    order_data["order_number"] = order_number

    email_sent = send_order_email(order_data, screenshot_path)

    return JSONResponse({
        "success": True,
        "order_number": order_number,
        "created_at": created_at,
        "total": total,
        "estimated_days": ESTIMATED_DAYS,
        "email_sent": email_sent,
    })


@app.get("/api/health")
async def health():
    return {"status": "ok", "business": BUSINESS_NAME}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"\n{'='*50}")
    print(f"  {BUSINESS_NAME} Order System")
    print(f"{'='*50}")
    print(f"  Local:  http://localhost:{port}")
    print(f"  Email:  {BUSINESS_EMAIL}")
    print(f"{'='*50}\n")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
