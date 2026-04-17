# Exercise 1 — Vending Machine dApp

A decentralised vending machine on Ethereum (Ganache). Users connect a wallet, browse products, buy items, and track ownership — all backed by an on-chain smart contract.

---

## Setup

### Prerequisites
- Node.js >= 18, npm
- Python >= 3.10
- Ganache CLI: `npm install -g ganache`

### 1. Start Ganache

```bash
ganache --deterministic
```

### 2. Install Node dependencies & deploy

```bash
cd implementation/exercise-1
npm install
npx hardhat compile
npx hardhat run scripts/deploy.ts --network ganache
```

Copy the printed contract address.

### 3. Configure app/.env

```bash
cp app/.env.example app/.env
# Edit app/.env — set CONTRACT_ADDRESS to the deployed address
# PRIVATE_KEY is Ganache account #0 from the deterministic mnemonic
```

### 4. Run tests

```bash
npx hardhat test
```

### 5. Start Flask app

```bash
cd app
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

---

## Design Choices

### What is on-chain and why

| Data | On-chain | Reason |
|------|----------|--------|
| Product catalog (name, price, stock) | ✓ | Authoritative trustless state |
| Purchase ownership | ✓ | Provable without a central DB |
| ETH payments | ✓ | Native to EVM; accumulates in contract until owner withdraws |
| Purchase history | ✓ (events) | Permanent, gas-efficient vs storage |

### What is off-chain and why

| Data | Off-chain | Reason |
|------|-----------|--------|
| Product emojis | Flask dict | Storing decorative strings on-chain wastes gas |
| Flash messages | Flask session | Ephemeral UI state, irrelevant to contract |
| Wallet private key | .env file | Never touches the chain |
| Admin auth UI | Flask 403 check | Defence-in-depth; contract also guards with onlyOwner |

---

## Test Cases

| # | Test | What it verifies |
|---|------|-----------------|
| 1 | Successful single purchase | Stock decreases, ownership increases |
| 2 | Successful multi-qty purchase | ownership[buyer][id] == qty |
| 3 | Fail — insufficient payment | reverts "Insufficient payment" |
| 4 | Fail — out of stock | reverts "Insufficient stock" |
| 5 | Fail — non-owner restock | reverts "Not owner" |
| 6 | Owner restock + event | Stock increases, ProductRestocked emitted |
| 7 | State after purchase | Both stock and ownership verified post-buy |
