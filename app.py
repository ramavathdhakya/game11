from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from models import db, User, Bet, WalletTransaction
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import requests
import os
import traceback

load_dotenv()

BIGBALL_API_KEY = os.getenv("BIGBALL_API_KEY") or os.getenv("BIGG_BALL_API")
BIGBALL_API_URL = "https://api.bigballsdata.com/v1/cricket/matches"

IST = timezone(timedelta(hours=5, minutes=30))


ALLOWED_REFILL_AMOUNTS = {500, 1000, 2000}

# n8n helper (set both in .env)
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")
N8N_SECRET = os.getenv("N8N_SECRET")


def _parse_positive_int(raw):
    """Return a positive int from a plain ASCII digit string, else None.

    Rejects things like "²" (isdigit() is True but int() fails) and
    absurdly long inputs, so bad form data can't cause a 500 error.
    """
    raw = (raw or "").strip()
    if not raw or len(raw) > 12 or not (raw.isascii() and raw.isdecimal()):
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _short_name(team):
    if team.get("short_name"):
        return team["short_name"]
    return team.get("name", "TBA")[:3].upper()


def _get_logo(team):
    return (
        team.get("logo")
        or team.get("logo_url")
        or team.get("crest")
        or team.get("flag")
        or team.get("image")
        or None
    )


def _format_kickoff(kickoff_utc):
    try:
        dt = datetime.strptime(kickoff_utc, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except (ValueError, TypeError):
        return kickoff_utc or "TBA"


def _map_status(api_status):
    mapping = {
        "scheduled": "upcoming",
        "live": "live",
        "finished": "finished",
    }
    return mapping.get(api_status, api_status)


def get_current_cricket_matches(match_id=None):
    today = datetime.now(timezone.utc).date().isoformat()
    params = {"date": today}
    headers = {"Authorization": f"Bearer {BIGBALL_API_KEY}"}

    try:
        response = requests.get(BIGBALL_API_URL, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        raw_matches = response.json().get("data", [])
        print("API returned", len(raw_matches), "matches:", [m.get("id") for m in raw_matches])
    except requests.RequestException as e:
        print("API call failed:", e)
        return []

    matches = []
    for m in raw_matches:
        if match_id and str(m.get("id")) != str(match_id):
            continue
        home = m.get("home") or {}
        away = m.get("away") or {}
        api_status = m.get("status", "scheduled")

        matches.append({
            "match_id": m.get("id"),
            "format": m.get("league", "Cricket"),
            "status": _map_status(api_status),
            "match_time": _format_kickoff(m.get("kickoff_utc")),
            "venue": m.get("venue", "TBA"),
            "team1": {
                "name": home.get("name", "TBA"),
                "short": _short_name(home),
                "logo": _get_logo(home),
                "odds": 2.0,
            },
            "team2": {
                "name": away.get("name", "TBA"),
                "short": _short_name(away),
                "logo": _get_logo(away),
                "odds": 2.0,
            },
            "betting_open": api_status == "scheduled" and m.get("has_odds", False),
        })

    return matches


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-123")
database_url = os.getenv("DATABASE_URL", "sqlite:///app.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
db.init_app(app)


with app.app_context():
    db.create_all()


@app.context_processor
def inject_user():
    user_id = session.get("user_id")
    user = User.query.get(user_id) if user_id else None
    return {"user": user}


@app.template_filter("coins")
def format_coins(value):
    return f"{value:,}"


@app.route("/")
def home():
    matches = get_current_cricket_matches()
    return render_template("index.html", matches=matches)


@app.route("/match/<match_id>")
def match_detail(match_id):
    matches = get_current_cricket_matches(match_id)
    if not matches:
        flash("Match not found.")
        return redirect(url_for("home"))
    match = matches[0]
    return render_template("match.html", match=match)


@app.route("/match/<match_id>/bet", methods=["POST"])
def place_bet(match_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in to place a bet.")
        return redirect(url_for("login"))

    matches = get_current_cricket_matches(match_id)
    if not matches:
        flash("Match not found.")
        return redirect(url_for("home"))
    match = matches[0]

    if not match["betting_open"]:
        flash("Betting is closed for this match.")
        return redirect(url_for("match_detail", match_id=match_id))

    team_picked = request.form.get("team_picked", "").strip()
    stake_raw = request.form.get("stake", "").strip()

    stake = _parse_positive_int(stake_raw)

    if team_picked not in (match["team1"]["name"], match["team2"]["name"]) or stake is None:
        flash("Please pick a team and enter a valid stake.")
        return redirect(url_for("match_detail", match_id=match_id))

    user = User.query.get(user_id)
    if not user:
        session.pop("user_id", None)
        flash("Please log in to place a bet.")
        return redirect(url_for("login"))

    if stake > user.coins:
        flash("Invalid stake amount.")
        return redirect(url_for("match_detail", match_id=match_id))

    odds = match["team1"]["odds"] if team_picked == match["team1"]["name"] else match["team2"]["odds"]

    bet = Bet(
        user_id=user.id,
        match_id=str(match_id),
        team_picked=team_picked,
        stake=stake,
        odds=odds,
    )
    user.coins -= stake

    db.session.add(bet)
    db.session.commit()

    flash(f"Bet placed on {team_picked} for {stake} coins!")
    return redirect(url_for("match_detail", match_id=match_id))


@app.route("/match/<match_id>/leaderboard")
def match_leaderboard(match_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in to view this leaderboard.")
        return redirect(url_for("login"))

    has_bet = Bet.query.filter_by(user_id=user_id, match_id=str(match_id)).first()

    if not has_bet:
        return render_template("leaderboard.html", bets=None, match_id=match_id, has_bet=False)

    bets = Bet.query.filter_by(match_id=str(match_id)).order_by(Bet.winnings.desc()).all()
    user_rank = next((i + 1 for i, b in enumerate(bets) if b.user_id == user_id), None)

    return render_template(
        "leaderboard.html",
        bets=bets,
        match_id=match_id,
        has_bet=True,
        user_rank=user_rank,
    )


@app.route("/my-bets")
def my_bets():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in to view your bets.")
        return redirect(url_for("login"))

    bets = Bet.query.filter_by(user_id=user_id).order_by(Bet.id.desc()).all()

    total_staked = sum(b.stake for b in bets)
    total_winnings = sum(b.winnings for b in bets if b.status == "won")

    return render_template(
        "my_bets.html",
        bets=bets,
        total_staked=total_staked,
        total_winnings=total_winnings,
    )


@app.route("/wallet")
def wallet():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in to view your wallet.")
        return redirect(url_for("login"))

    user = User.query.get(user_id)
    if not user:
        session.pop("user_id", None)
        return redirect(url_for("login"))

    spends = Bet.query.filter_by(user_id=user_id).order_by(Bet.id.desc()).all()
    refills = (
        WalletTransaction.query
        .filter_by(user_id=user_id, type="refill")
        .order_by(WalletTransaction.id.desc())
        .all()
    )

    low_balance = user.coins < 500

    return render_template(
        "wallet.html",
        spends=spends,
        refills=refills,
        low_balance=low_balance,
    )


@app.route("/wallet/refill", methods=["POST"])
def wallet_refill():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in to refill your wallet.")
        return redirect(url_for("login"))

    amount_raw = request.form.get("amount", "").strip()
    amount = _parse_positive_int(amount_raw)
    if amount not in ALLOWED_REFILL_AMOUNTS:
        flash("Please choose a valid refill amount.")
        return redirect(url_for("wallet"))

    user = User.query.get(user_id)
    if not user:
        session.pop("user_id", None)
        return redirect(url_for("login"))
    user.coins += amount

    txn = WalletTransaction(user_id=user.id, type="refill", amount=amount, note="Wallet top-up")
    db.session.add(txn)
    db.session.commit()

    flash(f"{amount} coins added to your wallet!")
    return redirect(url_for("wallet"))


def build_helper_context(user_id):
    """Collect ONLY this player's data. Works with SQLite and Postgres.
    This is sent to n8n together with the question."""
    user = User.query.get(user_id)
    bets = Bet.query.filter_by(user_id=user_id).order_by(Bet.id.desc()).all()
    refills = (
        WalletTransaction.query
        .filter_by(user_id=user_id, type="refill")
        .order_by(WalletTransaction.id.desc())
        .limit(10)
        .all()
    )
    matches = get_current_cricket_matches()[:15]

    return {
        "coins": user.coins if user else 0,
        "total_bets": len(bets),
        "total_staked": sum(b.stake for b in bets),
        "total_winnings": sum((b.winnings or 0) for b in bets if b.status == "won"),
        "latest_bets": [
            {
                "match_id": b.match_id,
                "team_picked": b.team_picked,
                "stake": b.stake,
                "odds": b.odds,
                "status": b.status,
                "winnings": b.winnings or 0,
                "potential_winnings": round(b.stake * b.odds),
            }
            for b in bets[:20]
        ],
        "latest_refills": [t.amount for t in refills],
        "todays_matches": [
            {
                "match_id": m["match_id"],
                "league": m["format"],
                "teams": f'{m["team1"]["name"]} vs {m["team2"]["name"]}',
                "status": m["status"],
                "start_time_ist": m["match_time"],
                "venue": m["venue"],
                "odds": {m["team1"]["name"]: m["team1"]["odds"], m["team2"]["name"]: m["team2"]["odds"]},
                "betting_open": m["betting_open"],
            }
            for m in matches
        ],
    }


@app.route("/ask", methods=["POST"])
def ask():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"answer": "Please log in to use the helper."}), 401

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()[:500]
    if not question:
        return jsonify({"answer": "Please type a question."})

    if not N8N_WEBHOOK_URL or not N8N_SECRET:
        return jsonify({"answer": "The helper is not set up yet."})

    try:
        resp = requests.post(
            N8N_WEBHOOK_URL,
            json={"question": question, "context": build_helper_context(user_id)},
            headers={"X-Secret": N8N_SECRET},
            timeout=25,
        )
        print("n8n replied with status:", resp.status_code)
        if resp.status_code >= 400:
            print("n8n error text:", resp.text[:300])
        resp.raise_for_status()

        body = resp.json()
        if isinstance(body, list) and body:  # n8n can send a list
            body = body[0]
        answer = (body.get("answer") if isinstance(body, dict) else None) or "Sorry, I have no answer for that."
    except Exception:
        # Show the REAL error in the Flask terminal, but always send JSON back
        traceback.print_exc()
        answer = "Sorry, the helper is not working right now. Please try again later."

    return jsonify({"answer": answer})


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        flash("You are already logged in")
        return redirect(url_for("home"))
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            flash(f"Welcome back! {user.username}")
            return redirect(url_for("home"))
        flash("Invalid username/email or password.")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not username or not email or not password:
            flash("Please fill out all the fields")
            return redirect(url_for("register"))
        if User.query.filter_by(username=username).first():
            flash("Username already taken")
            return redirect(url_for("register"))
        if User.query.filter_by(email=email).first():
            flash("Email already exists")
            return redirect(url_for("register"))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Account created! Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    flash("You have been logged out.")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")