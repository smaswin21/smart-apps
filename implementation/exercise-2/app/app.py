import os
import json
import sqlite3
import bcrypt
from pathlib import Path
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, abort, session)
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "ticketmarket-dev-secret"

MODE = os.getenv("MODE", "web2")

# ── Off-chain emoji map (used in both modes) ────────────────────────────────
EVENT_EMOJIS = {
    1: "🎸",
    2: "🎤",
}

def get_emoji(event_id: int) -> str:
    return EVENT_EMOJIS.get(event_id, "🎟")

# ════════════════════════════════════════════════════════════════════════════
# WEB2 — SQLite helpers
# ════════════════════════════════════════════════════════════════════════════

DB_PATH = Path(__file__).parent / "tickets.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            venue TEXT NOT NULL,
            total_tickets INTEGER NOT NULL,
            price_eth REAL NOT NULL,
            available INTEGER NOT NULL,
            emoji TEXT NOT NULL DEFAULT '🎟'
        );
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            for_resale INTEGER DEFAULT 0,
            resale_price_eth REAL,
            FOREIGN KEY(event_id) REFERENCES events(id),
            FOREIGN KEY(owner_id) REFERENCES users(id)
        );
    """)
    # Seed admin user
    admin_pw = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
    conn.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, is_admin) VALUES (?,?,1)",
        ("admin", admin_pw)
    )
    # Seed regular users
    for uname in ("alice", "bob"):
        pw = bcrypt.hashpw(uname.encode(), bcrypt.gensalt()).decode()
        conn.execute(
            "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?,?)",
            (uname, pw)
        )
    # Seed 2 events
    conn.execute(
        "INSERT OR IGNORE INTO events (id,name,date,venue,total_tickets,price_eth,available,emoji) "
        "VALUES (1,'Rock Night','2026-05-10','The Venue',100,0.01,100,'🎸')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO events (id,name,date,venue,total_tickets,price_eth,available,emoji) "
        "VALUES (2,'Jazz Evening','2026-05-17','Blue Note',50,0.005,50,'🎤')"
    )
    conn.commit()
    conn.close()

def current_user_id():
    return session.get("user_id")

def require_login():
    if not current_user_id():
        return redirect(url_for("login"))
    return None

def is_admin():
    uid = current_user_id()
    if not uid:
        return False
    conn = get_db()
    row = conn.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return row and row["is_admin"] == 1

# ── Web2 routes ─────────────────────────────────────────────────────────────

if MODE == "web2":

    @app.route("/")
    def index():
        redir = require_login()
        if redir:
            return redir
        conn = get_db()
        events = conn.execute("SELECT * FROM events").fetchall()
        conn.close()
        return render_template("index.html", events=events, mode=MODE,
                               identity=session.get("username"))

    @app.route("/event/<int:event_id>")
    def event_detail(event_id):
        redir = require_login()
        if redir:
            return redir
        conn = get_db()
        ev = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        conn.close()
        if not ev:
            abort(404)
        return render_template("event.html", event=ev, mode=MODE,
                               identity=session.get("username"))

    @app.route("/event/<int:event_id>/buy", methods=["POST"])
    def buy_ticket(event_id):
        redir = require_login()
        if redir:
            return redir
        conn = get_db()
        ev = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        if not ev or ev["available"] < 1:
            flash("Sold out or event not found.", "error")
            conn.close()
            return redirect(url_for("index"))
        conn.execute("UPDATE events SET available = available - 1 WHERE id=?", (event_id,))
        conn.execute("INSERT INTO tickets (event_id, owner_id) VALUES (?,?)",
                     (event_id, current_user_id()))
        conn.commit()
        conn.close()
        flash("Ticket purchased!", "success")
        return redirect(url_for("my_tickets"))

    @app.route("/my-tickets")
    def my_tickets():
        redir = require_login()
        if redir:
            return redir
        conn = get_db()
        rows = conn.execute(
            "SELECT t.id, t.for_resale, t.resale_price_eth, e.name, e.emoji, e.date "
            "FROM tickets t JOIN events e ON t.event_id=e.id "
            "WHERE t.owner_id=?", (current_user_id(),)
        ).fetchall()
        conn.close()
        return render_template("my_tickets.html", tickets=rows, mode=MODE,
                               identity=session.get("username"))

    @app.route("/my-tickets/<int:ticket_id>/list", methods=["POST"])
    def list_for_resale(ticket_id):
        redir = require_login()
        if redir:
            return redir
        price = float(request.form["resale_price"])
        conn = get_db()
        row = conn.execute("SELECT owner_id FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if not row or row["owner_id"] != current_user_id():
            abort(403)
        conn.execute("UPDATE tickets SET for_resale=1, resale_price_eth=? WHERE id=?",
                     (price, ticket_id))
        conn.commit()
        conn.close()
        flash("Ticket listed for resale.", "success")
        return redirect(url_for("my_tickets"))

    @app.route("/my-tickets/<int:ticket_id>/delist", methods=["POST"])
    def delist_ticket(ticket_id):
        redir = require_login()
        if redir:
            return redir
        conn = get_db()
        row = conn.execute("SELECT owner_id FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if not row or row["owner_id"] != current_user_id():
            abort(403)
        conn.execute("UPDATE tickets SET for_resale=0, resale_price_eth=NULL WHERE id=?",
                     (ticket_id,))
        conn.commit()
        conn.close()
        flash("Listing cancelled.", "success")
        return redirect(url_for("my_tickets"))

    @app.route("/resale")
    def resale():
        redir = require_login()
        if redir:
            return redir
        conn = get_db()
        rows = conn.execute(
            "SELECT t.id, t.resale_price_eth, t.owner_id, e.name, e.emoji, "
            "u.username as seller "
            "FROM tickets t JOIN events e ON t.event_id=e.id "
            "JOIN users u ON t.owner_id=u.id "
            "WHERE t.for_resale=1"
        ).fetchall()
        conn.close()
        return render_template("resale.html", listings=rows, mode=MODE,
                               identity=session.get("username"))

    @app.route("/resale/<int:ticket_id>/buy", methods=["POST"])
    def buy_resale(ticket_id):
        redir = require_login()
        if redir:
            return redir
        conn = get_db()
        row = conn.execute("SELECT * FROM tickets WHERE id=? AND for_resale=1",
                           (ticket_id,)).fetchone()
        if not row or row["owner_id"] == current_user_id():
            flash("Cannot buy this ticket.", "error")
            conn.close()
            return redirect(url_for("resale"))
        conn.execute("UPDATE tickets SET owner_id=?, for_resale=0, resale_price_eth=NULL WHERE id=?",
                     (current_user_id(), ticket_id))
        conn.commit()
        conn.close()
        flash("Resale ticket purchased!", "success")
        return redirect(url_for("my_tickets"))

    @app.route("/transfer", methods=["POST"])
    def transfer_ticket():
        redir = require_login()
        if redir:
            return redir
        ticket_id = int(request.form["ticket_id"])
        to_username = request.form["to_username"].strip()
        conn = get_db()
        row = conn.execute("SELECT owner_id, for_resale FROM tickets WHERE id=?",
                           (ticket_id,)).fetchone()
        if not row or row["owner_id"] != current_user_id():
            abort(403)
        if row["for_resale"]:
            flash("Delist ticket before transferring.", "error")
            conn.close()
            return redirect(url_for("my_tickets"))
        to_user = conn.execute("SELECT id FROM users WHERE username=?",
                               (to_username,)).fetchone()
        if not to_user:
            flash(f"User '{to_username}' not found.", "error")
            conn.close()
            return redirect(url_for("my_tickets"))
        conn.execute("UPDATE tickets SET owner_id=? WHERE id=?",
                     (to_user["id"], ticket_id))
        conn.commit()
        conn.close()
        flash(f"Ticket transferred to {to_username}.", "success")
        return redirect(url_for("my_tickets"))

    @app.route("/admin")
    def admin():
        if not is_admin():
            abort(403)
        conn = get_db()
        events = conn.execute("SELECT * FROM events").fetchall()
        conn.close()
        return render_template("admin.html", events=events, mode=MODE,
                               identity=session.get("username"))

    @app.route("/admin/create-event", methods=["POST"])
    def admin_create_event():
        if not is_admin():
            abort(403)
        name = request.form["name"].strip()
        date = request.form["date"].strip()
        venue = request.form["venue"].strip()
        total = int(request.form["total_tickets"])
        price = float(request.form["price_eth"])
        emoji = request.form.get("emoji", "🎟").strip() or "🎟"
        conn = get_db()
        conn.execute(
            "INSERT INTO events (name,date,venue,total_tickets,price_eth,available,emoji) "
            "VALUES (?,?,?,?,?,?,?)",
            (name, date, venue, total, price, total, emoji)
        )
        conn.commit()
        conn.close()
        flash(f"Event '{name}' created.", "success")
        return redirect(url_for("admin"))

    @app.route("/admin/release-tickets", methods=["POST"])
    def admin_release_tickets():
        if not is_admin():
            abort(403)
        event_id = int(request.form["event_id"])
        qty = int(request.form["qty"])
        conn = get_db()
        conn.execute("UPDATE events SET available=available+?, total_tickets=total_tickets+? WHERE id=?",
                     (qty, qty, event_id))
        conn.commit()
        conn.close()
        flash(f"Released {qty} extra tickets.", "success")
        return redirect(url_for("admin"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            action = request.form.get("action", "login")
            username = request.form["username"].strip()
            password = request.form["password"].encode()
            conn = get_db()
            if action == "register":
                pw_hash = bcrypt.hashpw(password, bcrypt.gensalt()).decode()
                try:
                    conn.execute("INSERT INTO users (username, password_hash) VALUES (?,?)",
                                 (username, pw_hash))
                    conn.commit()
                    flash("Account created — please log in.", "success")
                except sqlite3.IntegrityError:
                    flash("Username already taken.", "error")
                conn.close()
                return redirect(url_for("login"))
            else:
                row = conn.execute("SELECT * FROM users WHERE username=?",
                                   (username,)).fetchone()
                conn.close()
                if row and bcrypt.checkpw(password, row["password_hash"].encode()):
                    session["user_id"] = row["id"]
                    session["username"] = row["username"]
                    session["is_admin"] = bool(row["is_admin"])
                    return redirect(url_for("index"))
                flash("Invalid credentials.", "error")
        return render_template("login.html", mode=MODE)

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    init_db()

# ════════════════════════════════════════════════════════════════════════════
# WEB3 — web3.py helpers
# ════════════════════════════════════════════════════════════════════════════

if MODE == "web3":
    from web3 import Web3

    RPC_URL          = os.getenv("RPC_URL", "http://127.0.0.1:8545")
    PRIVATE_KEY      = os.getenv("PRIVATE_KEY")
    CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")

    if not PRIVATE_KEY or not CONTRACT_ADDRESS:
        raise RuntimeError(
            "Missing PRIVATE_KEY or CONTRACT_ADDRESS in app/.env (required for web3 mode)"
        )

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    account = w3.eth.account.from_key(PRIVATE_KEY)
    WALLET = account.address

    ARTIFACT_PATH = (
        Path(__file__).parent.parent
        / "artifacts" / "contracts" / "TicketMarket.sol" / "TicketMarket.json"
    )
    with open(ARTIFACT_PATH) as f:
        ABI = json.load(f)["abi"]

    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI)

    def send_tx(fn, value_wei=0):
        nonce = w3.eth.get_transaction_count(WALLET)
        tx = fn.build_transaction({
            "from": WALLET,
            "value": value_wei,
            "nonce": nonce,
            "gas": 300000,
            "gasPrice": w3.eth.gas_price,
        })
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        raw = getattr(signed, "rawTransaction", None) or getattr(signed, "raw_transaction")
        tx_hash = w3.eth.send_raw_transaction(raw)
        w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    def is_owner():
        return WALLET.lower() == contract.functions.owner().call().lower()

    def parse_event(e):
        return {
            "id": e[0], "name": e[1], "date": e[2], "venue": e[3],
            "total_tickets": e[4], "available": e[5],
            "price_eth": w3.from_wei(e[6], "ether"),
            "price_wei": e[6],
            "emoji": get_emoji(e[0]),
        }

    def parse_ticket(t):
        return {
            "id": t[0], "event_id": t[1], "owner": t[2],
            "for_resale": t[3], "resale_price_eth": w3.from_wei(t[4], "ether"),
            "resale_price_wei": t[4],
        }

    @app.route("/")
    def index():
        raw = contract.functions.getEvents().call()
        events = [parse_event(e) for e in raw]
        return render_template("index.html", events=events, mode=MODE,
                               identity=f"{WALLET[:6]}...{WALLET[-4:]}")

    @app.route("/event/<int:event_id>")
    def event_detail(event_id):
        e = contract.functions.events(event_id).call()
        event = parse_event(e)
        return render_template("event.html", event=event, mode=MODE,
                               identity=f"{WALLET[:6]}...{WALLET[-4:]}")

    @app.route("/event/<int:event_id>/buy", methods=["POST"])
    def buy_ticket(event_id):
        e = contract.functions.events(event_id).call()
        price_wei = e[6]
        try:
            tx = send_tx(contract.functions.buyTicket(event_id), value_wei=price_wei)
            flash(f"Ticket purchased! Tx: {tx}", "success")
        except Exception as ex:
            flash(f"Purchase failed: {ex}", "error")
        return redirect(url_for("my_tickets"))

    @app.route("/my-tickets")
    def my_tickets():
        raw = contract.functions.getTicketsByOwner(WALLET).call()
        tickets_data = []
        for t in raw:
            ticket = parse_ticket(t)
            ev = contract.functions.events(ticket["event_id"]).call()
            ticket["name"] = ev[1]
            ticket["emoji"] = get_emoji(ticket["event_id"])
            ticket["date"] = ev[2]
            tickets_data.append(ticket)
        return render_template("my_tickets.html", tickets=tickets_data, mode=MODE,
                               identity=f"{WALLET[:6]}...{WALLET[-4:]}")

    @app.route("/my-tickets/<int:ticket_id>/list", methods=["POST"])
    def list_for_resale(ticket_id):
        price_eth = float(request.form["resale_price"])
        price_wei = w3.to_wei(price_eth, "ether")
        try:
            tx = send_tx(contract.functions.listForResale(ticket_id, price_wei))
            flash(f"Listed for resale! Tx: {tx}", "success")
        except Exception as ex:
            flash(f"List failed: {ex}", "error")
        return redirect(url_for("my_tickets"))

    @app.route("/my-tickets/<int:ticket_id>/delist", methods=["POST"])
    def delist_ticket(ticket_id):
        try:
            tx = send_tx(contract.functions.delistTicket(ticket_id))
            flash(f"Delisted. Tx: {tx}", "success")
        except Exception as ex:
            flash(f"Delist failed: {ex}", "error")
        return redirect(url_for("my_tickets"))

    @app.route("/resale")
    def resale():
        raw = contract.functions.getResaleTickets().call()
        listings = []
        for t in raw:
            ticket = parse_ticket(t)
            ev = contract.functions.events(ticket["event_id"]).call()
            ticket["name"] = ev[1]
            ticket["emoji"] = get_emoji(ticket["event_id"])
            ticket["seller"] = f"{ticket['owner'][:6]}...{ticket['owner'][-4:]}"
            listings.append(ticket)
        return render_template("resale.html", listings=listings, mode=MODE,
                               identity=f"{WALLET[:6]}...{WALLET[-4:]}")

    @app.route("/resale/<int:ticket_id>/buy", methods=["POST"])
    def buy_resale(ticket_id):
        t = contract.functions.tickets(ticket_id).call()
        price_wei = t[4]  # resalePrice
        try:
            tx = send_tx(contract.functions.buyResaleTicket(ticket_id), value_wei=price_wei)
            flash(f"Resale ticket purchased! Tx: {tx}", "success")
        except Exception as ex:
            flash(f"Purchase failed: {ex}", "error")
        return redirect(url_for("my_tickets"))

    @app.route("/transfer", methods=["POST"])
    def transfer_ticket():
        ticket_id = int(request.form["ticket_id"])
        to_address = request.form["to_address"].strip()
        try:
            tx = send_tx(contract.functions.transferTicket(ticket_id, Web3.to_checksum_address(to_address)))
            flash(f"Ticket transferred! Tx: {tx}", "success")
        except Exception as ex:
            flash(f"Transfer failed: {ex}", "error")
        return redirect(url_for("my_tickets"))

    @app.route("/admin")
    def admin():
        if not is_owner():
            abort(403)
        raw = contract.functions.getEvents().call()
        events = [parse_event(e) for e in raw]
        return render_template("admin.html", events=events, mode=MODE,
                               identity=f"{WALLET[:6]}...{WALLET[-4:]}")

    @app.route("/admin/create-event", methods=["POST"])
    def admin_create_event():
        if not is_owner():
            abort(403)
        name  = request.form["name"].strip()
        date  = request.form["date"].strip()
        venue = request.form["venue"].strip()
        total = int(request.form["total_tickets"])
        price_wei = w3.to_wei(float(request.form["price_eth"]), "ether")
        emoji = request.form.get("emoji", "🎟").strip() or "🎟"
        try:
            raw = contract.functions.getEvents().call()
            next_id = max((e[0] for e in raw), default=0) + 1
            EVENT_EMOJIS[next_id] = emoji
            tx = send_tx(contract.functions.createEvent(name, date, venue, total, price_wei))
            flash(f"Event '{name}' created! Tx: {tx}", "success")
        except Exception as ex:
            flash(f"Create event failed: {ex}", "error")
        return redirect(url_for("admin"))

    @app.route("/admin/release-tickets", methods=["POST"])
    def admin_release_tickets():
        if not is_owner():
            abort(403)
        event_id = int(request.form["event_id"])
        qty = int(request.form["qty"])
        try:
            tx = send_tx(contract.functions.releaseTickets(event_id, qty))
            flash(f"Released {qty} tickets. Tx: {tx}", "success")
        except Exception as ex:
            flash(f"Release failed: {ex}", "error")
        return redirect(url_for("admin"))

    @app.route("/login")
    def login():
        return redirect(url_for("index"))

    @app.route("/logout", methods=["POST"])
    def logout():
        return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
