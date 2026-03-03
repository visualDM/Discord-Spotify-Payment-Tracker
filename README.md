# Discord Spotify Payment Tracker

A Discord bot that helps Spotify Family Plan groups track member payments. Members are organized into "family" groups, monthly subscription costs are automatically deducted from each member's balance, and GCash payments can be detected automatically via Gmail.

A companion **web dashboard** (Flask) is also included for a browser-based view of all groups and balances.

---

## Features

- Create and manage Spotify Family groups directly in Discord
- Track individual member balances with automatic monthly deductions
- Set a custom billing day for automatic monthly charges
- Manually record payments or let the bot detect GCash transfers via Gmail
- Web dashboard for a quick overview of all groups and balances
- Notifications to members with negative balances after each billing cycle

---

## Requirements

- Python 3.8+
- A Discord bot token ([create one here](https://discord.com/developers/applications))
- A Gmail account that receives GCash payment notifications (optional, for auto-detection)
- A Gmail [App Password](https://myaccount.google.com/apppasswords) for the account above

---

## Setup

### 1. Install dependencies

```bash
cd spotify_bot
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
DISCORD_TOKEN=your_discord_bot_token_here
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_gmail_app_password_here
```

> **Note:** `EMAIL_USER` and `EMAIL_PASS` are optional. If omitted, automatic GCash payment detection is disabled.

### 3. Run the bot

**Windows:**
```bat
run.bat
```

**Linux / macOS:**
```bash
cd spotify_bot
python main.py
```

### 4. Run the web dashboard (optional)

**Windows:**
```bat
run_web.bat
```

**Linux / macOS:**
```bash
cd spotify_bot
python web_app.py
```

The dashboard will be available at `http://127.0.0.1:5000`.

---

## Discord Commands

| Command | Description |
|---|---|
| `!create_family <name>` | Create a new Spotify Family group |
| `!join <name>` | Join an existing family group |
| `!leave` | Leave your current family group |
| `!delete_family` | Delete your family group (requires confirmation) |
| `!status` | Show balances for all members in your family |
| `!pay <amount> [@member]` | Add funds to yourself or a family member |
| `!cost <amount>` | Set the monthly deduction cost for your family (in PHP) |
| `!billing_day <day>` | Set the day of the month for automatic billing (1–31) |
| `!advance` | Manually trigger monthly deduction for your family |
| `!link_gcash <full name>` | Link your GCash name for automatic payment detection |
| `!add_users @User1 @User2 ...` | Add multiple users to your family at once |

---

## How It Works

1. A member creates a family group with `!create_family`.
2. Other members join with `!join <name>`.
3. The monthly cost (default: **56 PHP**, adjustable with `!cost`) is deducted from every member's balance on the configured billing day, automatically or via `!advance`.
4. Members top up their balance with `!pay`.
5. If Gmail credentials are configured, the bot checks for unread GCash notification emails every 60 seconds and automatically credits the matching member's balance.
6. Members with a negative balance are mentioned in the group channel after each billing cycle.

---

## Project Structure

```
spotify_bot/
├── main.py          # Discord bot entry point and commands
├── database.py      # SQLite database helpers
├── email_checker.py # GCash payment detection via Gmail IMAP
├── web_app.py       # Flask web dashboard
├── templates/
│   └── index.html   # Dashboard template
├── .env.example     # Environment variable template
├── requirements.txt # Python dependencies
├── run.bat          # Windows launcher for the bot
└── run_web.bat      # Windows launcher for the web dashboard
```

---

## License

This project is provided as-is for personal use.
