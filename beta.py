from flask import Flask, render_template, redirect, url_for, request, session, flash
from models import db, User, Bet, WalletTransaction
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import requests
import os

load_dotenv()

BIGBALL_API_KEY = os.getenv("BIGBALL_API_KEY") or os.getenv("BIGG_BALL_API")
BIGBALL_API_URL = "https://api.bigballsdata.com/v1/cricket/matches"

IST = timezone(timedelta(hours=5, minutes=30))


ALLOWED_REFILL_AMOUNTS = {500, 1000, 2000}


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


def fetch_match_by_id(match_id):
    """Ask the API for ONE match by its id (works for old matches too)."""
    headers = {"Authorization": f"Bearer {BIGBALL_API_KEY}"}
    try:
        response = requests.get(f"{BIGBALL_API_URL}/{match_id}", headers=headers, timeout=5)
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as e:
        print("Match lookup failed:", match_id, e)
        return None

    match = body.get("data", body) if isinstance(body, dict) else None
    return match if isinstance(match, dict) else None


def get_match_result(match_id):
    """Return None if the match is not ready to settle.
    Otherwise return {"winner": team name or None for a tie, "home": name, "away": name}.
    """
    match = fetch_match_by_id(match_id)
    if not match or match.get("status") != "finished":
        return None

    score = match.get("score") or {}
    try:
        home_score = int(score.get("home"))
        away_score = int(score.get("away"))
    except (TypeError, ValueError):
        return None  # no score yet -> do not settle

    home_name = (match.get("home") or {}).get("name")
    away_name = (match.get("away") or {}).get("name")
    if not home_name or not away_name:
        return None

    if home_score > away_score:
        winner = home_name
    elif away_score > home_score:
        winner = away_name
    else:
        winner = None  # tie

    return {"winner": winner, "home": home_name, "away": away_name}


def settle_pending_bets(user_id=None, match_id=None):
    """Mark pending bets as won / lost / refunded and pay the coins."""
    query = Bet.query.filter_by(status="pending")
    if user_id:
        query = query.filter_by(user_id=user_id)
    if match_id:
        query = query.filter_by(match_id=str(match_id))
    pending = query.all()
    if not pending:
        return

    # group bets by match, so we call the API only once per match
    by_match = {}
    for bet in pending:
        by_match.setdefault(bet.match_id, []).append(bet)

    for mid, bets in by_match.items():
        result = get_match_result(mid)
        if result is None:
            continue  # not finished / no score yet: try again later

        for bet in bets:
            if bet.team_picked not in (result["home"], result["away"]):
                continue  # team name does not match the API: leave it pending

            if result["winner"] is None:
                new_status, winnings, payout = "refunded", 0, bet.stake
            elif bet.team_picked == result["winner"]:
                winnings = int(bet.stake * bet.odds)
                new_status, payout = "won", winnings
            else:
                new_status, winnings, payout = "lost", 0, 0

            # Only ONE request can change a bet from "pending", so nobody is paid twice.
            changed = Bet.query.filter_by(id=bet.id, status="pending").update(
                {"status": new_status, "winnings": winnings},
                synchronize_session=False,
            )
            if changed == 1 and payout:
                User.query.filter_by(id=bet.user_id).update(
                    {"coins": User.coins + payout},
                    synchronize_session=False,
                )

    db.session.commit()


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-123")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
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

    settle_pending_bets(match_id=match_id)

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

    settle_pending_bets(user_id=user_id)

    bets = Bet.query.filter_by(user_id=user_id).order_by(Bet.id.desc()).all()

    total_staked = sum(b.stake for b in bets)
    total_winnings = sum(b.winnings for b in bets if b.status == "won")

    return render_template(
        "my_bets-beta.html",
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

    settle_pending_bets(user_id=user_id)

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