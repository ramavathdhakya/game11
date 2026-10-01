from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


db = SQLAlchemy()


def utcnow():
    """Naive UTC datetime (what we store in the database)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    coins = db.Column(db.Integer, default=1000)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Match(db.Model):
    """A match saved from the API, so pages read from our DB instead of
    calling the API on every request."""
    __tablename__ = "Matches"
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    league = db.Column(db.String(100), default="Cricket")
    status = db.Column(db.String(20), default="upcoming")  # upcoming / live / finished / other API status
    kickoff_utc = db.Column(db.DateTime, nullable=True, index=True)
    venue = db.Column(db.String(150), default="TBA")

    team1_name = db.Column(db.String(100), default="TBA")
    team1_short = db.Column(db.String(10), default="TBA")
    team1_logo = db.Column(db.String(500))

    team2_name = db.Column(db.String(100), default="TBA")
    team2_short = db.Column(db.String(10), default="TBA")
    team2_logo = db.Column(db.String(500))

    # Odds live in our own DB, fixed at 2.0 by default.
    # Change these later if you want dynamic odds.
    odds_team1 = db.Column(db.Float, default=2.0)
    odds_team2 = db.Column(db.Float, default=2.0)

    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)


class Bet(db.Model):
    __tablename__ = "Bets"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=False)
    match_id = db.Column(db.String(50), nullable=False)
    team_picked = db.Column(db.String(100), nullable=False)
    stake = db.Column(db.Integer, nullable=False)
    odds = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending / won / lost
    winnings = db.Column(db.Integer, default=0)

    user = db.relationship("User", backref="bets")


class WalletTransaction(db.Model):
    __tablename__ = "WalletTransactions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # "refill" or "spend"
    amount = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(120))

    user = db.relationship("User", backref="wallet_transactions")