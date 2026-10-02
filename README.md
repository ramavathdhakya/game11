                      GAME 11
-------------------------------------------------

Game 11 is a cricket practice-betting website. People use **virtual coins only**. No real money is used.

It is made with Python (Flask), HTML, CSS and JavaScript. It runs on Render.com.

---

## 1. What the website can do

- Make an account and log in (with username or email).
- Show today's cricket matches. The data comes from the BigBall API.
- Show match time in Indian time (IST).
- Show if betting is open or closed for each match.
- Let a logged-in user bet coins on a team.
- Show a wallet with a coin balance. The user can add 500, 1000 or 2000 coins.
- Show "My Bets" with total bets, total coins staked, and total winnings.
- Show a leaderboard for each match. The leaderboard unlocks only after the user bets on that match.
- Work on phones, with a menu button for small screens.

Every new user starts with **1000 coins**.

---

## 2. Tools used

| Tool | What it does |
|---|---|
| Python and Flask | The main website code |
| Flask-SQLAlchemy | Talks to the database |
| SQLite | Small database on your own computer |
| PostgreSQL | Real database on Render |
| psycopg | Lets Python talk to PostgreSQL |
| requests | Calls the BigBall API |
| python-dotenv | Reads secret keys from a `.env` file |
| gunicorn | The server that runs the site on Render |
| GitHub | Keeps the code online |
| Render.com | Puts the website on the internet |

---

## 3. Folder structure

```
game11/
├── main.py              (the main code: pages and logic)
├── models.py            (the database tables)
├── requirements.txt     (list of Python packages)
├── .gitignore           (files Git must ignore)
├── README.md            (this file)
├── templates/           (HTML pages)
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── match.html
│   ├── my_bets.html
│   ├── leaderboard.html
│   └── wallet.html
└── static/
    ├── css/
    │   └── style.css    (the design)
    └── js/
        └── app.js       (small JavaScript)
```

Important: HTML files must be in `templates`. CSS and JS must be in `static`. If they are in the wrong place, the site will not find them.

`my-bets-beta.html` is an extra test page. The code does not use it.

---

## 4. What each file does

**main.py**
- Sets up Flask and the database.
- Asks the BigBall API for today's matches.
- Has all the pages (routes):
  - `/` home page with matches
  - `/match/<id>` one match page
  - `/match/<id>/bet` place a bet
  - `/match/<id>/leaderboard` match leaderboard
  - `/my-bets` bet history
  - `/wallet` wallet page
  - `/wallet/refill` add coins
  - `/login`, `/register`, `/logout`
- Checks the stake and the team so bad data cannot break the site.
- Makes the database tables when the app starts (`db.create_all()`).

**models.py** (database tables)
- `User`: username, email, password (saved as a hash, not plain text), coins.
- `Bet`: user, match, team picked, stake, odds, status, winnings.
- `WalletTransaction`: coin refills.
- `Match`: a table for saving matches. It is not used yet.

**base.html**: the top menu, the footer and the flash messages. All other pages use it.

**app.js**: hides flash messages after 5 seconds and opens or closes the phone menu.

---

## 5. How a bet works

1. The home page asks the API for today's matches.
2. Betting is open only if the match status is "scheduled" and the API says `has_odds` is true.
3. The user picks a team and types a stake.
4. The code checks that the user is logged in, the team is right, and the stake is a positive number that is not more than their coins.
5. The stake is taken from the user's coins and the bet is saved as "pending".

Odds are fixed at 2.0 for both teams.

---

## 6. How I built this project from zero

Follow these steps in order. Test after each step, so a mistake is easy to find.

### Step 1: Get ready
1. Install Python (version 3.10 or newer) from python.org.
2. Make a new folder called `game11` and open it in PyCharm or VS Code.
3. Open the terminal inside that folder.

### Step 2: Make a virtual environment
A virtual environment keeps this project's packages apart from other projects.

```
python -m venv venv
```

Turn it on:

```
venv\Scripts\activate        (Windows)
source venv/bin/activate     (Mac or Linux)
```

You will see `(venv)` at the start of the terminal line.

### Step 3: Install the packages

```
pip install flask flask-sqlalchemy python-dotenv requests
```

### Step 4: Make the folders
Make these empty folders and files:

```
game11/
├── main.py
├── models.py
├── .env
├── templates/
└── static/
    ├── css/
    └── js/
```

### Step 5: Write the database tables (`models.py`)
Tables are the places where data is saved. I made four:

- `User`: username, email, password hash, coins (starts at 1000)
- `Bet`: user, match id, team picked, stake, odds, status, winnings
- `WalletTransaction`: coin refills
- `Match`: saved match data (not used yet)

Example of the `User` table:

```python
class User(db.Model):
    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    coins = db.Column(db.Integer, default=1000)
```

Passwords are never saved as plain text. I used `generate_password_hash` and `check_password_hash` from werkzeug.

### Step 6: Set up the app (`main.py`)
Start with the basic setup:

```python
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-123")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
db.init_app(app)

with app.app_context():
    db.create_all()      # makes the tables
```

The `.env` file is read by `load_dotenv()` at the top of the file.

### Step 7: Write the pages one by one
Add one page (route) at a time and test it in the browser each time. I did them in this order:

1. **Register and Login** (`/register`, `/login`, `/logout`). After login, the user id is saved in `session`.
2. **Home page** (`/`). It calls the BigBall API and shows today's matches.
3. **Match page** (`/match/<match_id>`). It shows one match and the bet form.
4. **Place bet** (`/match/<match_id>/bet`). It checks the data, takes coins from the user, and saves the bet.
5. **My Bets** (`/my-bets`). It lists the user's bets and the totals.
6. **Wallet** (`/wallet` and `/wallet/refill`). It shows the balance and lets the user add coins.
7. **Leaderboard** (`/match/<match_id>/leaderboard`). It opens only if the user has a bet on that match.

A route looks like this:

```python
@app.route("/")
def home():
    matches = get_current_cricket_matches()
    return render_template("index.html", matches=matches)
```

### Step 8: Get matches from the API
The function `get_current_cricket_matches()` does these things:

1. Asks the BigBall API for today's matches. It sends the API key in the request header.
2. If the API fails, it returns an empty list, so the site does not crash.
3. Changes each match into a simple form with team names, logos, status, venue, time and odds.
4. Changes the time from UTC to IST.
5. Sets `betting_open` to true only when the status is "scheduled" and the API says the match has odds.

### Step 9: Make the HTML pages (`templates/`)
1. First make `base.html`. It has the top menu, the flash messages and the footer. Other pages sit inside its `{% block content %}`.
2. Then make the other pages. Each one starts with `{% extends 'base.html' %}`.

The pages are `index.html`, `match.html`, `login.html`, `register.html`, `my_bets.html`, `wallet.html` and `leaderboard.html`.

Two small tools I added in `main.py` for the pages:
- `inject_user()` gives every page the logged-in user, so the menu can show the name and coins.
- A `coins` filter shows numbers with commas, like `1,000`.

### Step 10: Add the design and JavaScript
1. `static/css/style.css`: colors, cards, buttons, and the phone layout.
2. `static/js/app.js`: hides flash messages after 5 seconds and opens the phone menu.

### Step 11: Make the code safe
- Check every form value before using it (`_parse_positive_int` allows only plain positive numbers).
- A bet is allowed only if the user is logged in, the team is one of the two teams, and the stake is not more than the user's coins.
- Only the amounts 500, 1000 and 2000 are allowed for a refill.
- Use `POST` for logout, bets and refills, not links.

### Step 12: Run and test on your computer

```
python main.py
```

Open `http://127.0.0.1:5000`. Test this list:

1. Make an account.
2. Log in and log out.
3. Open a match and place a bet.
4. Check the coins went down.
5. Open My Bets and Wallet.
6. Refill the wallet.
7. Open the leaderboard before and after a bet.

### Step 13: Put it online
When all tests pass, deploy the site. The steps are in section 8.

---

## 7. Run it on your own computer

1. Install the packages:

```
pip install -r requirements.txt
```

2. Make a file called `.env` in the main folder:

```
SECRET_KEY=put-a-long-random-text-here
BIGBALL_API_KEY=your-api-key
```

3. Start the site:

```
python main.py
```

4. Open `http://127.0.0.1:5000` in your browser.

On your computer the app uses SQLite (`app.db`), because there is no `DATABASE_URL`.

Never put the `.env` file on GitHub.

---

## 8. What I did to put it on Render (step by step)

### Step 1: Fix the folders
Put the HTML files in `templates/` and the CSS and JS files in `static/css/` and `static/js/`.

### Step 2: Make `requirements.txt`

```
Flask
Flask-SQLAlchemy
python-dotenv
requests
gunicorn
psycopg[binary]
```

### Step 3: Change the database code in `main.py`
SQLite files are deleted on every Render deploy, so I used a PostgreSQL database. The code reads the `DATABASE_URL` setting and changes the start of the link so it works with the psycopg driver:

```python
database_url = os.getenv("DATABASE_URL", "sqlite:///app.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
```

### Step 4: Make `.gitignore`

```
.env
__pycache__/
*.pyc
instance/
app.db
venv/
.idea/
```

### Step 5: Push the code to GitHub

```
git init
git add .
git commit -m "first commit"
git remote add origin https://github.com/YOUR-USERNAME/game11.git
git push -u origin master
```

My branch was called `master`, so I used `master` on Render too.

### Step 6: Make the database on Render
1. Render, then **New +**, then **PostgreSQL**.
2. Name: `game11-db`. Plan: **Free**.
3. Wait until it says **Available**.
4. Copy the **Internal Database URL**.

### Step 7: Make the web service on Render
1. **New +**, then **Web Service**, then choose the GitHub repository.
2. Fill in:
   - Branch: `master`
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn main:app`
   - Plan: Free

### Step 8: Add the environment variables

| Key | Value |
|---|---|
| `DATABASE_URL` | the Internal Database URL |
| `SECRET_KEY` | a long random text |
| `BIGBALL_API_KEY` | the BigBall API key |

To make a safe `SECRET_KEY`:

```
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 9: Deploy
Click **Create Web Service**. Open the **Logs** tab. When you see "Your service is live", the site is ready.

---

## 9. Problems I had and how I fixed them

| Problem | Why it happened | Fix |
|---|---|---|
| `error: src refspec main does not match any` | My branch was `master`, not `main` | Use `master` in the push command and on Render, or rename the branch with `git branch -M main` |
| `.idea/vcs.xml` showed as untracked | PyCharm makes this folder | Add `.idea/` to `.gitignore` |
| Weak `SECRET_KEY` | I first used normal words as the key | Make a random key and save it in Render's Environment page |
| `ModuleNotFoundError: No module named 'psycopg'` | The code used the psycopg driver, but it was not in `requirements.txt` | Add `psycopg[binary]` to `requirements.txt` and use `postgresql+psycopg://` in `main.py` |
| `gunicorn main:main` | Wrong Start Command | Use `gunicorn main:app`. The first part is the file name (`main`). The second part is the Flask variable name (`app`) |

---

## 10. How to check if the site is live

- Open the service on Render. A green **Live** badge means it is working.
- Open the **Logs** tab. Look for "Your service is live".
- Click the link at the top, like `https://game11.onrender.com`.
- Test: make an account, log in, refill the wallet, then refresh the page. If your coins are still there, the database works.

---

## 11. How to update the site

Change the code, then run:

```
git add .
git commit -m "what I changed"
git push
```

Render deploys the new version by itself.

---

## 12. How to stop or start the site

- **Stop for now:** Render, then your service, then **Settings**, then **Suspend Web Service**.
- **Start again:** open the service and click **Resume Service**. It does not restart by itself.
- **Delete forever:** Settings, then **Delete Web Service**.
- The database is separate. Stopping the website does not stop the database. Delete it from the database's own **Settings** page only if you do not need the data.

---

## 13. Things to remember

- The free web service sleeps after about 15 minutes with no visitors. The first visit after that can take 30 to 60 seconds.
- The free PostgreSQL database has a time limit. Check Render's pricing page for the current rule so you do not lose data.
- The API call asks only for today's matches. If there are no matches today, the home page says "No matches available right now".
- Keep `SECRET_KEY` and `BIGBALL_API_KEY` only in the Render Environment page or the `.env` file. Never in the code or on GitHub.

---

## 14. Not done yet

- **Bet settlement:** bets stay "pending". Nothing marks them as won or lost, and winners do not get paid yet. Winnings stay at 0.
- The `Match` table in `models.py` is not used yet.
- Odds are always 2.0.
- The test page `my-bets-beta.html` has a "Refunded" status, but the code does not use it yet.

# Game 11 Helper: n8n Setup

This file explains only the **n8n part** of the helper.

## How it works

1. A player types a question in the Help box on the website.
2. Flask collects **only that player's data** (coins, bets, refills, today's matches).
3. Flask sends the question and the data to n8n.
4. n8n asks the AI and sends the answer back.
5. Flask shows the answer in the Help box.

n8n does not read your database. Flask sends the data with the question, so this works with SQLite on your laptop. You do not need to deploy.

## What you need

- An n8n account
- An AI key. Pick one:
  - **Anthropic key** (needs paid credit): https://console.anthropic.com/settings/keys
  - **Google Gemini key** (free for testing): https://aistudio.google.com
- A secret password that you make up (example: `test123`)
- The file `n8n_system_message.txt` from this folder

## Step 1: Create the workflow

1. Log in to n8n.
2. Click **Create workflow**.
3. Name it `Game 11 Helper`.

## Step 2: Add the Webhook node

The Webhook is the door where Flask sends the question.

1. Click **Add first step** and search for `Webhook`. Click it.
2. Set these:

| Setting | Value |
|---|---|
| HTTP Method | `POST` (n8n starts with GET, so you must change it) |
| Path | `game11-helper` (no `/` at the start) |
| Authentication | `Header Auth` |
| Respond | `Using 'Respond to Webhook' Node` |

3. For **Authentication**, click **Create new credential**:
   - **Name:** `X-Secret`
   - **Value:** your made-up secret password
   - Click **Save**

Remember this password. You will put the same password in your `.env` file as `N8N_SECRET`.

## Step 3: Add the AI Agent node

1. Click the plus button after the Webhook node. Search `AI Agent` and add it.
2. Set **Source for Prompt** to `Define below`.
3. In **Prompt (User Message)**, paste this:

```
Player question: {{ $('Webhook').first().json.body.question }}

Player data (JSON): {{ JSON.stringify($('Webhook').first().json.body.context) }}
```

4. Click **Add Option** and choose **System Message**.
5. Open `n8n_system_message.txt`, copy all of it, and paste it into the System Message box.

## Step 4: Add the Chat Model

On the AI Agent node, click the plus button under **Chat Model**. Pick one option.

### Option A: Anthropic (paid credit)

1. Make a key in the Anthropic Console. Add some credit in Billing first.
2. In n8n, choose **Anthropic Chat Model**.
3. Click **Create new credential**, paste the key (it starts with `sk-ant-`), and **Save**.
4. In **Model**, pick a Claude Sonnet model.

### Option B: Google Gemini (free for testing)

1. Go to https://aistudio.google.com and sign in with Google.
2. Click **Get API key** and create a key. Copy it.
3. In n8n, choose **Google Gemini Chat Model**.
4. Click **Create new credential**, paste the key, and **Save**.
5. In **Model**, pick a Flash model.

Do not paste extra spaces with the key.

## Step 5: Add the Respond to Webhook node

1. Click the plus button after the AI Agent node. Search `Respond to Webhook` and add it.
2. Set these:

| Setting | Value |
|---|---|
| Respond With | `JSON` |
| Response Body | `{{ { "answer": $json.output } }}` |

3. Press `Ctrl+S` to save.

Your workflow should look like this:

```
Webhook -> AI Agent -> Respond to Webhook
              |
         Chat Model
```

## Step 6: Test n8n alone

1. Double-click the **Webhook** node.
2. At the top, click the **Test URL** tab and copy the link. It has `/webhook-test/` in it.
3. Click **Listen for test event**.
4. Right away, run this in your terminal. Use your Test URL and your secret:

```
curl -X POST "TEST_URL_HERE" -H "X-Secret: your-secret" -H "Content-Type: application/json" -d '{"question": "How many coins do I have?", "context": {"coins": 750, "total_bets": 1, "total_staked": 250, "total_winnings": 0, "latest_bets": [], "latest_refills": [], "todays_matches": []}}'
```

5. You should get `{"answer": "..."}` and the answer should say 750 coins.

Notes:
- The Test URL works for **one call** each time you click **Listen for test event**.
- Do not paste the link in the browser. A browser sends GET, but this webhook needs POST.

## Step 7: Make it live

1. Turn on the **Active** switch at the top right.
2. In the Webhook node, click the **Production URL** tab and copy the link. It has `/webhook/` in it.
3. Put these two lines in your project's `.env` file:

```
N8N_WEBHOOK_URL=your_production_url
N8N_SECRET=your_secret_password
```

The secret in `.env` must be exactly the same as the **Value** of the `X-Secret` credential in n8n.

## Common problems

| Problem | Fix |
|---|---|
| `This webhook is not registered for POST requests` | Set **HTTP Method** to `POST`, save, click **Listen for test event**, then send the request with curl. If you use the Production URL, switch the workflow off and on again. |
| `404` on the Test URL | Click **Listen for test event** first. The Test URL works for one call only. |
| `403` error | The secret or the name is wrong. The name must be `X-Secret`, and the value must match `.env`. |
| `404` on the Production URL | The workflow is not **Active**. |
| Answer says it has no data | Open the Webhook node output and check that `context` arrived. |
| `Invalid API key` | Paste the key again with no extra spaces. |
| `Credit balance too low` | Add credit in Anthropic Billing, or use the free Gemini option. |
| No matches in the answer | The BigBall API call may have failed. Look at the Flask terminal for `API call failed`. |

## Safety rules

- Never put your AI key or secret password in your Flask code or on GitHub.
- Keep `.env` out of GitHub.
- Use a long secret password before you deploy.
