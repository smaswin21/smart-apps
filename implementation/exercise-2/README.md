# Exercise 2 — Event Ticket Booking & Resale

A web2 + web3 implementation of an event ticketing app. Both versions share one Flask app and one set of templates. `MODE=web2|web3` in `app/.env` switches which backend is active.

---

## Prerequisites

- Python 3.10+
- Node 18+
- Ganache CLI: `npm install -g ganache`

---

## Install Dependencies

```bash
# Python
cd app
pip install -r requirements.txt

# Node
cd ..
npm install
```

---

## Running Web2

```bash
cd app
MODE=web2 python app.py
```

Open http://localhost:5000 and log in with one of these accounts:

| Username | Password | Role  |
|----------|----------|-------|
| admin    | admin123 | Admin (create events, release tickets) |
| alice    | alice    | User  |
| bob      | bob      | User  |

---

## Running Web3

**1. Start Ganache**

```bash
ganache --deterministic
```

**2. Compile and deploy the contract**

```bash
npx hardhat compile
npx hardhat run scripts/deploy.ts --network localhost
```

Copy the deployed contract address from the output.

**3. Configure `app/.env`**

```
MODE=web3
RPC_URL=http://127.0.0.1:8545
PRIVATE_KEY=<ganache account[0] private key>
CONTRACT_ADDRESS=<deployed address from step 2>
```

When using `--deterministic`, the default account[0] private key is:
`0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d`

**4. Run the app**

```bash
cd app
MODE=web3 python app.py
```

Open http://localhost:5000.

---

## Running Tests

```bash
npx hardhat test
```
