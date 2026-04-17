# Exercise 2 — Event Ticket Booking & Resale

A web2 + web3 implementation of an event ticketing app. Both versions share one Flask app and one set of templates. `MODE=web2|web3` in `.env` switches which backend is active.

---

## Setup

### Prerequisites
- Python 3.10+, Node 18+, Ganache CLI (`npm install -g ganache`)

### Install dependencies

```bash
# Python
cd app && pip install -r requirements.txt

# Node
cd .. && npm install
```

### Run web2

```bash
cd app
cp .env.example .env        # set MODE=web2
MODE=web2 python app.py
```

Open http://localhost:5000. Log in as:
- `admin` / `admin123` — can create events and release tickets
- `alice` / `alice` — regular user
- `bob` / `bob` — regular user

### Run web3

```bash
# 1. Start Ganache
ganache --deterministic

# 2. Compile & deploy
npx hardhat compile
npx hardhat run scripts/deploy.ts --network ganache

# 3. Set env
cd app && cp .env.example .env
# Fill in PRIVATE_KEY (Ganache account[0]) and CONTRACT_ADDRESS

# 4. Run
MODE=web3 python app.py
```

### Run tests

```bash
npx hardhat test
```

---

## Test Cases

| # | Test | What it checks |
|---|---|---|
| 1 | Successful ticket purchase | `buyTicket` records ownership in `ticketsByOwner` |
| 2 | Insufficient payment | Sending less than `priceWei` reverts with "Insufficient payment" |
| 3 | Successful transfer | `transferTicket` moves ticket to new owner, removes from old |
| 4 | Transfer by non-owner | Non-owner call reverts with "Not ticket owner" |
| 5 | Full resale flow | list → buy → seller paid, ownership transferred |
| 6 | Admin permission | Non-owner `createEvent` reverts with "Not owner" |
| 7 | Sold-out event | `buyTicket` on 0-available event reverts with "Sold out" |
| 8 | Ownership sequence | buy → list → resale buy: final owner is resale buyer, not original |

---

## Design Choices

### What is on-chain (web3)
- **Event catalog** — single source of truth; any client can read it without trusting a server
- **Ticket ownership** — who owns which ticket, enforced by the EVM, not a database
- **Resale price** — stored in the contract so payment and ownership transfer happen atomically
- **Payments** — ETH flows through the contract; resale proceeds go directly to seller via `call{value: price}`

### What is off-chain (web3)
- **Emojis** — cosmetic metadata; storing strings on-chain wastes gas
- **Flash messages** — ephemeral UI state, not business logic
- **Session/login** — web3 identity comes from the wallet; no server-side session needed

### Why this split?
Trust is the key question. Anything that needs to be trusted (ownership, price, supply) belongs on-chain. Anything purely presentational or ephemeral stays off-chain.

---

## Web2 vs Web3 Comparison

| Concern | Web2 | Web3 |
|---|---|---|
| Data storage | SQLite on the server | Ethereum contract storage |
| Who enforces rules | Flask application code | Solidity + EVM |
| User identity | Username + bcrypt password | Wallet private key |
| Admin access | `is_admin` DB flag + session | `onlyOwner` modifier (contract deployer) |
| Payments | Simulated (no value transfer) | Real ETH via `msg.value` |
| Ticket transfer | DB `UPDATE owner_id` | `transferTicket()` + event emitted |
| Resale atomicity | Two DB writes (can fail mid-way) | Single transaction: payment + ownership |
| Auditability | Server logs (centralised, mutable) | Immutable on-chain events |
| Trust model | Trust the operator | Trustless — verify on-chain |
| Offline resilience | Down if server is down | Contract persists as long as Ethereum runs |
