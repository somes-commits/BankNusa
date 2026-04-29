# 🏦 NusaBank — Digital Banking App

Aplikasi perbankan digital berbasis Flask + PostgreSQL, siap deploy ke **Vercel**.

---

## 📁 Struktur Proyek

```
nusabank/
├── api/
│   └── index.py          # Flask app (entry point Vercel)
├── templates/
│   ├── login.html         # Halaman login & register
│   └── dashboard.html     # Dashboard nasabah
├── static/               # Aset statis (CSS, JS, gambar)
├── vercel.json           # Konfigurasi Vercel
├── requirements.txt      # Dependensi Python
├── .env.example          # Contoh variabel lingkungan
└── README.md
```

---

## 🚀 Cara Deploy ke Vercel

### 1. Siapkan Database PostgreSQL

Pilih salah satu penyedia database gratis:

| Penyedia | URL Daftar | Keterangan |
|----------|-----------|------------|
| **Vercel Postgres** | vercel.com/storage | Integrasi langsung di Vercel dashboard |
| **Neon** | neon.tech | PostgreSQL serverless, gratis tier tersedia |
| **Supabase** | supabase.com | PostgreSQL + fitur ekstra, gratis tier tersedia |
| **Railway** | railway.app | Mudah digunakan, gratis tier tersedia |

Setelah membuat database, salin **Connection String** (format `postgresql://...`).

---

### 2. Deploy ke Vercel

#### Cara A — Via GitHub (Rekomendasi)

```bash
# 1. Push kode ke GitHub
git init
git add .
git commit -m "Initial commit NusaBank"
git remote add origin https://github.com/username/nusabank.git
git push -u origin main

# 2. Buka vercel.com → New Project → Import repo GitHub
# 3. Tambahkan Environment Variables (lihat langkah 3)
# 4. Klik Deploy
```

#### Cara B — Via Vercel CLI

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Deploy dari folder proyek
cd nusabank
vercel

# Untuk production
vercel --prod
```

---

### 3. Tambahkan Environment Variables di Vercel

Buka **Vercel Dashboard → Project → Settings → Environment Variables**, tambahkan:

| Nama Variabel | Nilai | Keterangan |
|---------------|-------|------------|
| `DATABASE_URL` | `postgresql://user:pass@host/db?sslmode=require` | Connection string PostgreSQL |
| `SECRET_KEY` | string acak panjang | Kunci enkripsi session Flask |

**Generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

### 4. Inisialisasi Database (WAJIB — lakukan sekali)

Setelah deploy, jalankan perintah berikut untuk membuat tabel dan data demo:

```bash
curl -X POST https://nama-app.vercel.app/api/setup
```

Atau buka di browser: `https://nama-app.vercel.app/api/setup` (gunakan tool seperti Postman/Hoppscotch dengan method POST).

---

### 5. Cek Status

```
GET https://nama-app.vercel.app/api/health
```

Respons sukses:
```json
{
  "success": true,
  "status": "ok",
  "db": "connected"
}
```

---

## 💻 Pengembangan Lokal

```bash
# 1. Clone / download proyek
cd nusabank

# 2. Buat virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Install dependensi
pip install -r requirements.txt

# 4. Salin dan isi file .env
cp .env.example .env
# Edit .env dengan DATABASE_URL dan SECRET_KEY

# 5. Jalankan aplikasi
python api/index.py

# 6. Inisialisasi database (sekali saja)
curl -X POST http://localhost:5000/api/setup

# Buka browser: http://localhost:5000
```

---

## 🔌 Daftar API Endpoint

| Method | Endpoint | Auth | Deskripsi |
|--------|----------|------|-----------|
| `POST` | `/api/setup` | ❌ | Inisialisasi database & seed data |
| `GET`  | `/api/health` | ❌ | Cek koneksi database |
| `POST` | `/api/login` | ❌ | Login nasabah |
| `POST` | `/api/logout` | ❌ | Logout |
| `POST` | `/api/register` | ❌ | Daftar akun baru |
| `GET`  | `/api/profile` | ✅ | Data profil & saldo |
| `GET`  | `/api/saldo` | ✅ | Cek saldo |
| `POST` | `/api/transfer` | ✅ | Transfer dana |
| `GET`  | `/api/transaksi` | ✅ | Riwayat transaksi |
| `GET`  | `/api/cari-rekening/<no>` | ✅ | Cari pemilik rekening |

---

## 👤 Akun Demo

| Nama | Email | Password | No. Rekening | Saldo |
|------|-------|----------|--------------|-------|
| Budi Santoso | budi@email.com | budi123 | 1234567890 | Rp 5.000.000 |
| Siti Rahayu | siti@email.com | siti123 | 0987654321 | Rp 3.500.000 |
| Ahmad Fauzi | ahmad@email.com | ahmad123 | 1122334455 | Rp 8.750.000 |

---

## 🛠 Tech Stack

- **Backend**: Python 3.9+ · Flask 3 · psycopg2
- **Database**: PostgreSQL (Vercel Postgres / Neon / Supabase)
- **Hosting**: Vercel (Serverless Functions)
- **Frontend**: Vanilla HTML/CSS/JS (no framework)
