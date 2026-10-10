"""
FinSavvy — Be smarter with money.
Flask backend: auth, module progress, and saved "Think Before You Decide" sessions.

Run:
    pip install -r requirements.txt
    python app.py

Server starts on http://localhost:5000
Database: a local SQLite file `finsavvy.db`, created automatically on first run.
"""

import sqlite3
import secrets
import datetime
from functools import wraps

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = "finsavvy.db"

app = Flask(__name__)
CORS(app)  # allows the frontend (served from a different port/file) to call this API


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS module_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            module_id TEXT NOT NULL,
            percent INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, module_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            income REAL, savings REAL, expenses REAL,
            purchase REAL, method TEXT, rate REAL, tenure INTEGER,
            reflection TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def require_auth(f):
    """Decorator: reads 'Authorization: Bearer <token>', attaches g.user_id."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed Authorization header"}), 401
        token = auth_header.split(" ", 1)[1]

        db = get_db()
        row = db.execute("SELECT user_id FROM tokens WHERE token = ?", (token,)).fetchone()
        if row is None:
            return jsonify({"error": "Invalid or expired token"}), 401

        g.user_id = row["user_id"]
        return f(*args, **kwargs)
    return wrapper


def issue_token(user_id):
    token = secrets.token_hex(24)
    db = get_db()
    db.execute(
        "INSERT INTO tokens (token, user_id, created_at) VALUES (?, ?, ?)",
        (token, user_id, datetime.datetime.utcnow().isoformat()),
    )
    db.commit()
    return token


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or "@" not in email:
        return jsonify({"error": "A valid email is required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        return jsonify({"error": "An account with this email already exists"}), 409

    password_hash = generate_password_hash(password)
    cur = db.execute(
        "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
        (email, password_hash, datetime.datetime.utcnow().isoformat()),
    )
    db.commit()
    user_id = cur.lastrowid

    token = issue_token(user_id)
    return jsonify({"token": token, "email": email}), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Incorrect email or password"}), 401

    token = issue_token(user["id"])
    return jsonify({"token": token, "email": email}), 200


# ---------------------------------------------------------------------------
# Module progress routes
# ---------------------------------------------------------------------------

@app.route("/api/progress", methods=["GET"])
@require_auth
def get_progress():
    db = get_db()
    rows = db.execute(
        "SELECT module_id, percent, updated_at FROM module_progress WHERE user_id = ?",
        (g.user_id,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/progress", methods=["POST"])
@require_auth
def save_progress():
    data = request.get_json(force=True) or {}
    module_id = data.get("module_id")
    percent = data.get("percent")

    if not module_id or percent is None:
        return jsonify({"error": "module_id and percent are required"}), 400
    try:
        percent = max(0, min(100, int(percent)))
    except (TypeError, ValueError):
        return jsonify({"error": "percent must be a number"}), 400

    db = get_db()
    db.execute(
        """
        INSERT INTO module_progress (user_id, module_id, percent, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, module_id)
        DO UPDATE SET percent = excluded.percent, updated_at = excluded.updated_at
        """,
        (g.user_id, module_id, percent, datetime.datetime.utcnow().isoformat()),
    )
    db.commit()
    return jsonify({"module_id": module_id, "percent": percent}), 200


# ---------------------------------------------------------------------------
# Decisions routes (Think Before You Decide history)
# ---------------------------------------------------------------------------

@app.route("/api/decisions", methods=["GET"])
@require_auth
def get_decisions():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM decisions WHERE user_id = ? ORDER BY created_at DESC",
        (g.user_id,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/decisions", methods=["POST"])
@require_auth
def save_decision():
    data = request.get_json(force=True) or {}
    db = get_db()
    db.execute(
        """
        INSERT INTO decisions
            (user_id, income, savings, expenses, purchase, method, rate, tenure, reflection, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            g.user_id,
            data.get("income"), data.get("savings"), data.get("expenses"),
            data.get("purchase"), data.get("method"), data.get("rate"), data.get("tenure"),
            data.get("reflection"),
            datetime.datetime.utcnow().isoformat(),
        ),
    )
    db.commit()
    return jsonify({"status": "saved"}), 201


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
