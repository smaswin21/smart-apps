import os
import json
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "vending-machine-dev-secret"

# --- Web3 setup ---
RPC_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")

if not PRIVATE_KEY or not CONTRACT_ADDRESS:
    raise RuntimeError(
        "Missing required env vars. Copy app/.env.example to app/.env and fill in "
        "PRIVATE_KEY and CONTRACT_ADDRESS before starting the app."
    )

w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = w3.eth.account.from_key(PRIVATE_KEY)
WALLET_ADDRESS = account.address

# Load ABI from compiled artifact
ARTIFACT_PATH = Path(__file__).parent.parent / "artifacts" / "contracts" / "VendingMachine.sol" / "VendingMachine.json"
with open(ARTIFACT_PATH) as f:
    artifact = json.load(f)
ABI = artifact["abi"]

contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI)

# Product emojis (off-chain — not stored on-chain)
PRODUCT_EMOJIS = {
    "Cola": "🥤",
    "Chocolate": "🍫",
    "Coffee": "☕",
    "Juice": "🧃",
}

def get_emoji(name: str) -> str:
    return PRODUCT_EMOJIS.get(name, "🛒")

def send_transaction(fn):
    """Build, sign, and send a contract transaction. Returns tx hash string."""
    nonce = w3.eth.get_transaction_count(WALLET_ADDRESS)
    tx = fn.build_transaction({
        "from": WALLET_ADDRESS,
        "nonce": nonce,
        "gas": 200000,
        "gasPrice": w3.eth.gas_price,
    })
    signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    raw = getattr(signed, "rawTransaction", None) or getattr(signed, "raw_transaction")
    tx_hash = w3.eth.send_raw_transaction(raw)
    w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_hash.hex()


@app.route("/")
def index():
    raw_products = contract.functions.getProducts().call()
    products = []
    for p in raw_products:
        products.append({
            "id": p[0],
            "name": p[1],
            "price_wei": p[2],
            "price_eth": w3.from_wei(p[2], "ether"),
            "stock": p[3],
            "emoji": get_emoji(p[1]),
        })
    return render_template("index.html", products=products, wallet=WALLET_ADDRESS)


@app.route("/buy", methods=["POST"])
def buy():
    product_id = int(request.form["product_id"])
    qty = int(request.form["qty"])
    try:
        # Read current price from contract
        product = contract.functions.products(product_id).call()
        price_wei = product[2]
        total_wei = price_wei * qty

        nonce = w3.eth.get_transaction_count(WALLET_ADDRESS)
        tx = contract.functions.buyProduct(product_id, qty).build_transaction({
            "from": WALLET_ADDRESS,
            "value": total_wei,
            "nonce": nonce,
            "gas": 200000,
            "gasPrice": w3.eth.gas_price,
        })
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        raw = getattr(signed, "rawTransaction", None) or getattr(signed, "raw_transaction")
        tx_hash = w3.eth.send_raw_transaction(raw)
        w3.eth.wait_for_transaction_receipt(tx_hash)
        flash(f"Purchase successful! Tx: {tx_hash.hex()}", "success")
    except Exception as e:
        flash(f"Transaction failed: {str(e)}", "error")
    return redirect(url_for("index"))


@app.route("/my-items")
def my_items():
    raw_products = contract.functions.getProducts().call()
    items = []
    for p in raw_products:
        owned = contract.functions.getOwnershipCount(WALLET_ADDRESS, p[0]).call()
        items.append({
            "id": p[0],
            "name": p[1],
            "emoji": get_emoji(p[1]),
            "owned": owned,
        })
    return render_template("my_items.html", items=items, wallet=WALLET_ADDRESS)


@app.route("/admin")
def admin():
    contract_owner = contract.functions.owner().call()
    if WALLET_ADDRESS.lower() != contract_owner.lower():
        abort(403)
    raw_products = contract.functions.getProducts().call()
    products = [{"id": p[0], "name": p[1], "stock": p[3]} for p in raw_products]
    return render_template("admin.html", products=products, wallet=WALLET_ADDRESS)


@app.route("/admin/restock", methods=["POST"])
def admin_restock():
    contract_owner = contract.functions.owner().call()
    if WALLET_ADDRESS.lower() != contract_owner.lower():
        abort(403)
    product_id = int(request.form["product_id"])
    qty = int(request.form["qty"])
    try:
        tx_hash = send_transaction(contract.functions.restockProduct(product_id, qty))
        flash(f"Restocked successfully! Tx: {tx_hash}", "success")
    except Exception as e:
        flash(f"Restock failed: {str(e)}", "error")
    return redirect(url_for("admin"))


@app.route("/admin/add-product", methods=["POST"])
def admin_add_product():
    contract_owner = contract.functions.owner().call()
    if WALLET_ADDRESS.lower() != contract_owner.lower():
        abort(403)
    name = request.form["name"].strip()
    price_eth = float(request.form["price_eth"])
    price_wei = w3.to_wei(price_eth, "ether")
    stock = int(request.form["stock"])
    try:
        tx_hash = send_transaction(contract.functions.addProduct(name, price_wei, stock))
        flash(f"Product '{name}' added! Tx: {tx_hash}", "success")
    except Exception as e:
        flash(f"Add product failed: {str(e)}", "error")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
