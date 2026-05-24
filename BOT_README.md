# Polymarket BTC Up/Down Trading Bot

**Modal: $2 | Target: $10,000**
Markov Chain + Kelly Criterion | Self-learning loop

---

## Cara Kerja

Bot ini mengeksploitasi inefisiensi di pasar BTC 5-minute Up/Down Polymarket:
1. **Markov Chain** - menganalisis persistensi arah harga BTC
2. **Kelly Criterion** - menghitung ukuran taruhan optimal
3. **Entry filter** - hanya masuk jika p(j*,j*) >= 0.87 DAN edge >= 5%
4. **Journal** - mencatat semua trade untuk self-learning

---

## Setup di Windows (PowerShell + VS Code)

### Prasyarat

1. **Python 3.10+** - download dari [python.org](https://www.python.org/downloads/)
   - WAJIB centang **"Add Python to PATH"** saat install!
2. **VS Code** - download dari [code.visualstudio.com](https://code.visualstudio.com/)
3. **Git** - download dari [git-scm.com](https://git-scm.com/downloads)

### Step 1: Clone Repo

Buka PowerShell:
```powershell
git clone https://github.com/Winx0/Polyverse.git
cd Polyverse
```

### Step 2: Jalankan Setup

```powershell
.\setup.ps1
```

Ini akan:
- Cek Python terinstall
- Buat virtual environment
- Install semua dependencies
- Buat folder data/journal

### Step 3: Edit Konfigurasi

Buka `.env.bot` di VS Code:
```powershell
code .env.bot
```

Untuk **DRY RUN** (simulasi, tanpa uang asli):
```env
DRY_RUN=true
BANKROLL=2.00
```
Tidak perlu isi PRIVATE_KEY atau SAFE_ADDRESS.

Untuk **LIVE** trading (uang asli):
```env
DRY_RUN=false
BANKROLL=2.00
PRIVATE_KEY=0x_your_private_key_here
SAFE_ADDRESS=your_polymarket_safe_address
```

### Step 4: Jalankan Bot

**Quick test (5 menit, threshold rendah):**
```powershell
.\run_drytest.ps1
```

**Normal run (DRY RUN):**
```powershell
.\run.ps1
```

---

## Struktur File

```
Polyverse/
├── bot/
│   ├── __init__.py          # Package init
│   ├── main.py              # Entry point
│   ├── engine.py            # Trading loop utama
│   ├── markov.py            # Markov Chain model
│   ├── kelly.py             # Kelly Criterion sizing
│   ├── price_feed.py        # BTC price dari Binance
│   ├── polymarket_client.py # Polymarket CLOB v2 API
│   ├── journal.py           # Trade logging
│   └── telegram_notifier.py # Notifikasi Telegram
├── data/
│   └── journal/             # Trade logs (auto-created)
├── .env.bot                 # Konfigurasi (JANGAN commit!)
├── requirements.txt         # Python dependencies
├── setup.ps1                # Setup script
├── run.ps1                  # Run script
├── run_drytest.ps1          # Quick test script
└── BOT_README.md            # File ini
```

---

## Parameter Strategy

| Parameter | Default | Fungsi |
|-----------|---------|--------|
| `MIN_PROB` | 0.87 | Threshold Markov persistence minimum |
| `MIN_EDGE` | 0.05 | Gap minimum antara model vs market (5%) |
| `MIN_BET` | $0.50 | Taruhan minimum per trade |
| `MAX_BET` | $2.00 | Taruhan maximum per trade |
| `LOOP_INTERVAL` | 81s | Interval antar analisis |
| `BANKROLL` | $2.00 | Modal awal |

---

## Telegram Notifications (Optional)

1. Buka Telegram, chat @BotFather
2. Kirim `/newbot`, ikuti instruksi, dapat token
3. Chat @userinfobot untuk dapat chat_id
4. Isi di `.env.bot`:
```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v
TELEGRAM_CHAT_ID=123456789
```

---

## Roadmap: $2 → $10,000

| Phase | Modal | Max Bet | Strategy |
|-------|-------|---------|----------|
| 1. Training | $2 | $0.50 | DRY_RUN, kumpulkan data 50-100 trades |
| 2. Micro Live | $2 | $0.50 | Live, quarter-Kelly, sangat konservatif |
| 3. Growth | $10+ | $2.00 | Naikkan MAX_BET, self-learning aktif |
| 4. Scale | $100+ | $10.00 | Full Kelly, multi-window |
| 5. Target | $1000+ | $50.00 | Compound growth |

**PENTING:** Jangan skip Phase 1! Biarkan bot belajar dulu.

---

## Polymarket Wallet Setup (untuk LIVE trading)

1. Buka [polymarket.com](https://polymarket.com)
2. Connect wallet (MetaMask / Rabby)
3. Deposit USDC ke Polygon network ($2 minimum)
4. Approve 3 contracts di Settings:
   - CTF Exchange
   - Neg Risk CTF Exchange
   - Neg Risk Adapter
5. Copy SAFE_ADDRESS dari profil Polymarket
6. Export PRIVATE_KEY dari wallet (HATI-HATI!)

---

## Safety Notes

- **Selalu mulai dengan DRY_RUN=true**
- **Jangan commit .env.bot ke git** (sudah di .gitignore)
- **$2 adalah uang yang siap hilang** - ini bukan jaminan profit
- **Gunakan wallet terpisah** untuk trading bot (bukan wallet utama)
- **Monitor setiap hari** - cek journal dan Telegram reports
- Win rate 63-72% BUKAN berarti profit pasti - ada variance

---

## Troubleshooting

**Python not found:**
```powershell
# Cek PATH
python --version
# Jika error, reinstall Python dan centang "Add to PATH"
```

**Module not found:**
```powershell
# Pastikan venv aktif
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Binance API blocked:**
- Gunakan VPN jika Binance diblokir di region kamu
- Bot otomatis fallback ke CoinGecko

**Permission denied (PowerShell):**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
