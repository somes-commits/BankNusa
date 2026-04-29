"""
NusaBank — Flask CRUD API
Database  : PostgreSQL (Vercel Postgres / Neon / Supabase)
Hosting   : Vercel (Serverless Python)
"""

import os
import hashlib
import uuid
from datetime import datetime
from functools import wraps

import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv

# ── load .env di local dev ──
load_dotenv()

# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────
# Untuk Vercel, templates ada di ../templates (satu level atas /api)
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMPL_DIR   = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, template_folder=TMPL_DIR, static_folder=STATIC_DIR)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-nusabank-2024")
CORS(app, supports_credentials=True)

# ─────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────

def get_db():
    """
    Buka koneksi PostgreSQL dari DATABASE_URL.
    Vercel Postgres / Neon / Supabase semuanya kompatibel.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL tidak ditemukan. "
            "Tambahkan variabel lingkungan DATABASE_URL di Vercel Dashboard "
            "atau file .env untuk pengembangan lokal."
        )
    conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def init_db():
    """
    Buat tabel jika belum ada + seed data demo.
    Panggil sekali via endpoint /api/setup atau saat bootstrap.
    """
    conn = get_db()
    cur  = conn.cursor()

    # ── tabel users ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           TEXT PRIMARY KEY,
            nama         TEXT NOT NULL,
            email        TEXT UNIQUE NOT NULL,
            no_rekening  TEXT UNIQUE NOT NULL,
            password     TEXT NOT NULL,
            saldo        NUMERIC(18,2) DEFAULT 0,
            created_at   TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ── tabel transaksi ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transaksi (
            id               TEXT PRIMARY KEY,
            user_id          TEXT NOT NULL REFERENCES users(id),
            tipe             TEXT NOT NULL CHECK (tipe IN ('debit','kredit')),
            jumlah           NUMERIC(18,2) NOT NULL,
            keterangan       TEXT,
            rekening_tujuan  TEXT,
            nama_tujuan      TEXT,
            saldo_sebelum    NUMERIC(18,2),
            saldo_sesudah    NUMERIC(18,2),
            created_at       TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ── index supaya query cepat ──
    cur.execute("CREATE INDEX IF NOT EXISTS idx_trx_user ON transaksi(user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_trx_created ON transaksi(created_at DESC)")

    # ── seed demo users (idempotent) ──
    demo_users = [
        ("user-001", "Budi Santoso",  "budi@email.com",  "1234567890", hash_pwd("budi123"),  5_000_000),
        ("user-002", "Siti Rahayu",   "siti@email.com",  "0987654321", hash_pwd("siti123"),  3_500_000),
        ("user-003", "Ahmad Fauzi",   "ahmad@email.com", "1122334455", hash_pwd("ahmad123"), 8_750_000),
    ]
    for u in demo_users:
        cur.execute("""
            INSERT INTO users (id, nama, email, no_rekening, password, saldo)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO NOTHING
        """, u)

    conn.commit()
    cur.close()
    conn.close()

# ─────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────

def hash_pwd(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()


def fmt_rp(amount) -> str:
    return f"Rp {float(amount):,.0f}".replace(",", ".")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"success": False, "message": "Sesi berakhir. Silakan login kembali."}), 401
        return f(*args, **kwargs)
    return decorated


def gen_no_rekening(conn) -> str:
    """Generate nomor rekening 10 digit unik."""
    cur = conn.cursor()
    cur.execute("SELECT no_rekening FROM users ORDER BY created_at DESC LIMIT 1")
    row = cur.fetchone()
    cur.close()
    if row:
        last = int(row["no_rekening"])
        return str(last + 1).zfill(10)
    return "1000000001"

# ─────────────────────────────────────────────
# PAGE ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("index"))
    return render_template("dashboard.html")

# ─────────────────────────────────────────────
# SETUP / HEALTH
# ─────────────────────────────────────────────

@app.route("/api/setup", methods=["POST"])
def api_setup():
    """
    Inisialisasi database (buat tabel + seed data).
    Panggil SEKALI setelah deploy: POST /api/setup
    """
    try:
        init_db()
        return jsonify({"success": True, "message": "Database berhasil diinisialisasi."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/health")
def api_health():
    """Cek koneksi database."""
    try:
        conn = get_db()
        conn.close()
        return jsonify({"success": True, "status": "ok", "db": "connected"})
    except Exception as e:
        return jsonify({"success": False, "status": "error", "message": str(e)}), 500

# ─────────────────────────────────────────────
# AUTH API
# ─────────────────────────────────────────────

@app.route("/api/login", methods=["POST"])
def api_login():
    data     = request.get_json() or {}
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"success": False, "message": "Email dan password wajib diisi."}), 400

    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email, hash_pwd(password))
        )
        user = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({"success": False, "message": f"DB error: {e}"}), 500

    if not user:
        return jsonify({"success": False, "message": "Email atau password salah."}), 401

    session["user_id"] = user["id"]
    session["nama"]    = user["nama"]

    return jsonify({
        "success": True,
        "message": "Login berhasil.",
        "user": {
            "id":          user["id"],
            "nama":        user["nama"],
            "email":       user["email"],
            "no_rekening": user["no_rekening"],
        }
    })


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True, "message": "Logout berhasil."})


@app.route("/api/register", methods=["POST"])
def api_register():
    data     = request.get_json() or {}
    nama     = data.get("nama", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not all([nama, email, password]):
        return jsonify({"success": False, "message": "Semua field wajib diisi."}), 400
    if len(password) < 6:
        return jsonify({"success": False, "message": "Password minimal 6 karakter."}), 400

    try:
        conn = get_db()
        cur  = conn.cursor()

        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({"success": False, "message": "Email sudah terdaftar."}), 409

        user_id = "usr-" + str(uuid.uuid4())[:8]
        no_rek  = gen_no_rekening(conn)

        cur.execute("""
            INSERT INTO users (id, nama, email, no_rekening, password, saldo)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (user_id, nama, email, no_rek, hash_pwd(password), 1_000_000))

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({"success": False, "message": f"DB error: {e}"}), 500

    return jsonify({
        "success": True,
        "message": "Registrasi berhasil! Saldo awal Rp 1.000.000 telah diberikan."
    })

# ─────────────────────────────────────────────
# ACCOUNT API
# ─────────────────────────────────────────────

@app.route("/api/profile")
@login_required
def api_profile():
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id=%s", (session["user_id"],))
        user = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

    if not user:
        session.clear()
        return jsonify({"success": False, "message": "User tidak ditemukan."}), 404

    return jsonify({
        "success": True,
        "data": {
            "id":          user["id"],
            "nama":        user["nama"],
            "email":       user["email"],
            "no_rekening": user["no_rekening"],
            "saldo":       float(user["saldo"]),
            "saldo_fmt":   fmt_rp(user["saldo"]),
            "created_at":  str(user["created_at"]),
        }
    })


@app.route("/api/saldo")
@login_required
def api_saldo():
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("SELECT saldo FROM users WHERE id=%s", (session["user_id"],))
        row = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

    return jsonify({
        "success":   True,
        "saldo":     float(row["saldo"]),
        "saldo_fmt": fmt_rp(row["saldo"]),
    })

# ─────────────────────────────────────────────
# TRANSFER API
# ─────────────────────────────────────────────

@app.route("/api/transfer", methods=["POST"])
@login_required
def api_transfer():
    data             = request.get_json() or {}
    rekening_tujuan  = data.get("rekening_tujuan", "").strip()
    keterangan       = data.get("keterangan", "Transfer").strip() or "Transfer"

    try:
        jumlah = float(data.get("jumlah", 0))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Jumlah tidak valid."}), 400

    if not rekening_tujuan:
        return jsonify({"success": False, "message": "Nomor rekening tujuan wajib diisi."}), 400
    if jumlah < 10_000:
        return jsonify({"success": False, "message": "Minimal transfer Rp 10.000."}), 400

    try:
        conn = get_db()
        cur  = conn.cursor()

        # Ambil data pengirim (lock row)
        cur.execute("SELECT * FROM users WHERE id=%s FOR UPDATE", (session["user_id"],))
        pengirim = cur.fetchone()

        # Ambil data penerima (lock row)
        cur.execute("SELECT * FROM users WHERE no_rekening=%s FOR UPDATE", (rekening_tujuan,))
        penerima = cur.fetchone()

        if not penerima:
            cur.close(); conn.close()
            return jsonify({"success": False, "message": "Nomor rekening tujuan tidak ditemukan."}), 404

        if pengirim["no_rekening"] == rekening_tujuan:
            cur.close(); conn.close()
            return jsonify({"success": False, "message": "Tidak dapat transfer ke rekening sendiri."}), 400

        if float(pengirim["saldo"]) < jumlah:
            cur.close(); conn.close()
            return jsonify({"success": False, "message": "Saldo tidak mencukupi."}), 400

        saldo_p_before = float(pengirim["saldo"])
        saldo_p_after  = saldo_p_before - jumlah
        saldo_r_before = float(penerima["saldo"])
        saldo_r_after  = saldo_r_before + jumlah

        # Update saldo
        cur.execute("UPDATE users SET saldo=%s WHERE id=%s", (saldo_p_after,  pengirim["id"]))
        cur.execute("UPDATE users SET saldo=%s WHERE id=%s", (saldo_r_after,  penerima["id"]))

        now   = datetime.utcnow()
        trx_a = str(uuid.uuid4())
        trx_b = str(uuid.uuid4())

        # Catat transaksi pengirim → debit
        cur.execute("""
            INSERT INTO transaksi
              (id,user_id,tipe,jumlah,keterangan,rekening_tujuan,nama_tujuan,saldo_sebelum,saldo_sesudah,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (trx_a, pengirim["id"], "debit", jumlah, keterangan,
              rekening_tujuan, penerima["nama"], saldo_p_before, saldo_p_after, now))

        # Catat transaksi penerima → kredit
        cur.execute("""
            INSERT INTO transaksi
              (id,user_id,tipe,jumlah,keterangan,rekening_tujuan,nama_tujuan,saldo_sebelum,saldo_sesudah,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (trx_b, penerima["id"], "kredit", jumlah, f"Transfer dari {pengirim['nama']}",
              pengirim["no_rekening"], pengirim["nama"], saldo_r_before, saldo_r_after, now))

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        return jsonify({"success": False, "message": f"DB error: {e}"}), 500

    return jsonify({
        "success": True,
        "message": f"Transfer berhasil ke {penerima['nama']}.",
        "data": {
            "nama_penerima":  penerima["nama"],
            "rekening_tujuan": rekening_tujuan,
            "jumlah":          jumlah,
            "jumlah_fmt":      fmt_rp(jumlah),
            "saldo_baru":      saldo_p_after,
            "saldo_baru_fmt":  fmt_rp(saldo_p_after),
        }
    })

# ─────────────────────────────────────────────
# TRANSAKSI API
# ─────────────────────────────────────────────

@app.route("/api/transaksi")
@login_required
def api_transaksi():
    limit = min(int(request.args.get("limit", 20)), 100)

    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT * FROM transaksi
            WHERE user_id=%s
            ORDER BY created_at DESC
            LIMIT %s
        """, (session["user_id"], limit))
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

    result = []
    for r in rows:
        result.append({
            "id":               r["id"],
            "tipe":             r["tipe"],
            "jumlah":           float(r["jumlah"]),
            "jumlah_fmt":       fmt_rp(r["jumlah"]),
            "keterangan":       r["keterangan"],
            "rekening_tujuan":  r["rekening_tujuan"],
            "nama_tujuan":      r["nama_tujuan"],
            "saldo_sesudah":    float(r["saldo_sesudah"]) if r["saldo_sesudah"] else 0,
            "saldo_sesudah_fmt":fmt_rp(r["saldo_sesudah"]) if r["saldo_sesudah"] else "Rp 0",
            "created_at":       str(r["created_at"]),
        })

    return jsonify({"success": True, "data": result, "total": len(result)})

# ─────────────────────────────────────────────
# CARI REKENING API
# ─────────────────────────────────────────────

@app.route("/api/cari-rekening/<no_rek>")
@login_required
def api_cari_rekening(no_rek):
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute(
            "SELECT nama, no_rekening FROM users WHERE no_rekening=%s",
            (no_rek,)
        )
        user = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

    if not user:
        return jsonify({"success": False, "message": "Rekening tidak ditemukan."}), 404

    return jsonify({"success": True, "nama": user["nama"], "no_rekening": user["no_rekening"]})

# ─────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Local development
    init_db()
    app.run(debug=True, port=5000)
