# smartGame

smartGame is a SmartPy project for a two-player betting game based on a binary cellular automaton.

The project now uses a **hybrid settlement model**:

- **fast path**: both players reveal the same final bit off-chain and the contract pays immediately
- **forced path**: if they disagree or one refuses to finish the result workflow, the contract can compute the result on-chain **in batches**

This keeps the normal case cheap while ensuring that a dishonest loser cannot block the true winner forever.

The winner receives the full pot of `20 tez`.

---

## Project structure

```text
.
├── create_venv.sh
├── run.sh
├── tests.sh
├── contracts/
│   ├── main.py
│   ├── contract.py
│   ├── simulation.py
│   ├── utils.py
│   └── errors.py
├── tests/
│   ├── test_contract.py
│   ├── test_simulation.py
│   └── test_security.py
└── utils/
    └── logs.py
```

---

## Requirements

- Python `3.10` to `3.14`
- or Docker as fallback

---

## Setup

Prepare the virtual environment and install dependencies:

```bash
./create_venv.sh
```

---

## Manual simulation

Run the interactive simulator:

```bash
./run.sh
```

This runs the **Python reference simulation only**.
It does **not** execute the SmartPy contract.
It is useful to inspect the deterministic result for two secrets.

---

## Run tests

Execute all tests with:

```bash
./tests.sh
```

---

## Game flow

### 1. Join phase

Two players join the contract by sending exactly `10 tez` each and a commitment.

A commitment is a hash of:

- player address
- secret
- salt

### 2. Reveal phase

Each player reveals:

- their secret
- their salt

The contract verifies that the revealed data matches the original commitment.

### 3. Quick result phase

Each player may publish a commitment to the final bit, then reveal it.

- if both reveal the **same** final bit, the contract settles immediately
- if they disagree, the contract switches to forced on-chain resolution
- if one player stops cooperating, anyone can push the contract to forced resolution after timeout

### 4. Forced initialization phase

The contract reconstructs the initial automaton state from the two revealed secrets in batches.

### 5. Forced simulation phase

The contract executes the rule-150 ring automaton in batches until all rounds are completed.

### 6. Final settlement

The center bit of the final state decides the winner:

- `0` → player 1 wins
- `1` → player 2 wins

---

## Why this design is safer

The previous design had a weakness:

- if both players did not agree on the final bit, the game could end in a refund

The new design removes that weakness:

- agreement gives a cheap fast path
- disagreement triggers batched on-chain computation
- the true winner can still be determined automatically

---

## Security properties

The project includes protections for:

- wrong stake amount
- same player joining twice
- invalid reveal
- duplicate reveal
- non-registered reveal
- timeout before second player joins
- timeout during reveal
- disagreement on the final result
- non-cooperation during the quick result workflow

The contract uses:

- commit-reveal for secrets
- optional commit-reveal for quick result settlement
- deterministic state generation
- deterministic simulation
- forced batched on-chain settlement when needed

---

## Main files

### `contracts/contract.py`

SmartPy contract implementing:

- join
- reveal
- quick result commit / reveal
- forced batched initialization
- forced batched simulation
- timeout handling
- payout

### `contracts/simulation.py`

Python reference implementation of the same simulation logic.

### `contracts/main.py`

Interactive CLI simulator used by `run.sh`.

### `tests/test_simulation.py`

Checks the simulation logic.

### `tests/test_contract.py`

Checks the contract fast path and forced path.

### `tests/test_security.py`

Checks failure cases and security scenarios.

---

## Recommended usage

For normal local inspection:

```bash
./run.sh
```

For verification:

```bash
./tests.sh
```

---

## Warning

Do not run project scripts with `sudo` unless absolutely necessary.
