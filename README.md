# 💹 Finance Discord Bot

บอท Discord สำหรับติดตามพอร์ตหุ้น ข่าว และวิเคราะห์หลักทรัพย์แบบ real-time

---

## ✨ Features

- 📊 **Portfolio Tracking** — ติดตามหุ้นพร้อม P/L จริง แปลงเป็น THB อัตโนมัติ
- 📰 **News Feed** — ดูข่าวหุ้นรายตัวแบบ real-time
- 🔔 **Price Alerts** — แจ้งเตือนผ่าน DM เมื่อหุ้นถึงราคาเป้าหมาย
- 📈 **Stock Analysis** — วิเคราะห์ Technical + Institutional Holders + Sentiment
- 🌅 **Morning Report** — รายงานพอร์ตอัตโนมัติทุกเช้า

---

## 🤖 Commands

| Command | Description |
|--------|-------------|
| `!port` | ดู portfolio summary |
| `!addstock SYMBOL QTY COST` | เพิ่มหุ้น เช่น `!addstock NVDA 10 177.12` |
| `!removestock SYMBOL` | ลบหุ้นออกจาก portfolio |
| `!news SYMBOL` | ดูข่าวหุ้นรายตัว เช่น `!news AAPL` |
| `!analyze SYMBOL` | วิเคราะห์หุ้น (Technical + Big Money + Sentiment) |
| `!alert SYMBOL PRICE` | ตั้ง price alert เช่น `!alert NVDA 250` |
| `!alerts` | ดู alert ทั้งหมดที่ตั้งไว้ |
| `!removealert SYMBOL` | ลบ alert |
| `!report` | สร้าง morning report ทันที |
| `!help` | ดูคำสั่งทั้งหมด |

---

## 🚀 Getting Started

### 1. Clone repo

```bash
git clone https://github.com/kittiponglnwza/Finance-Discord-Bot.git
cd Finance-Discord-Bot
```

### 2. ติดตั้ง dependencies

```bash
pip install -r requirements.txt
```

### 3. ตั้งค่า Environment Variables

copy `.env.example` เป็น `.env` แล้วใส่ค่าจริง:

```env
DISCORD_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key
NEWSAPI_KEY=your_newsapi_key
MORNING_REPORT_CHANNEL_ID=your_channel_id
MORNING_REPORT_HOUR=7
MORNING_REPORT_MINUTE=0
MORNING_REPORT_TIMEZONE=Asia/Bangkok
```

### 4. รัน

```bash
python main.py
```

---

## ☁️ Deploy บน Railway

1. Push โค้ดขึ้น GitHub
2. ไปที่ [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. ตั้ง Environment Variables ใน Railway Dashboard
4. ตั้ง Start Command: `python main.py`

---

## 🗂️ Project Structure

```
Finance-Discord-Bot/
├── main.py                  # Entry point
├── requirements.txt
├── src/
│   ├── cogs/                # Discord command handlers
│   │   ├── alerts.py        # !alert commands
│   │   ├── analyze.py       # !analyze command
│   │   ├── news.py          # !news command
│   │   ├── portfolio.py     # !port, !addstock, !removestock
│   │   └── report.py        # !report, !help
│   ├── services/            # Business logic
│   │   ├── analyze.py       # Technical + Institutional + Sentiment
│   │   ├── news.py          # News fetching
│   │   ├── price.py         # Live price via yfinance
│   │   ├── scheduler.py     # Background jobs
│   │   └── sentiment.py     # AI summary via OpenAI
│   ├── db/                  # Database layer (SQLite)
│   │   ├── models.py
│   │   └── queries.py
│   └── utils/
│       ├── cache.py
│       └── formatter.py     # Discord embed builders
└── tests/
    └── test_all.py
```

---

## 🛠️ Tech Stack

- **Discord.py** — Discord bot framework
- **yfinance** — ดึงข้อมูลราคาหุ้น
- **OpenAI GPT-4o-mini** — AI สรุปข่าว
- **APScheduler** — งาน background อัตโนมัติ
- **aiosqlite** — database
- **Railway** — hosting

---

## ⚠️ Disclaimer

ข้อมูลในบอทนี้ไม่ใช่คำแนะนำการลงทุน ใช้เพื่อการศึกษาเท่านั้น
