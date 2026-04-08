# smartGame

smartGame is a SmartPy project for a two-player betting game based on a binary cellular automaton.

Each player commits a secret value, both players reveal their secrets, and the contract runs a deterministic simulation. The final output bit decides the winner:

- `0` → player 1 wins
- `1` → player 2 wins

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

This script:

- creates `.venv` if needed
- reuses it if it already exists
- installs or updates required dependencies
- falls back to Docker if no compatible local Python is found

---

## Manual simulation

Run the interactive simulator:

```bash
./run.sh
```

You will be asked to enter:

- player 1 secret
- player 2 secret

The project parameters are fixed in code.

The simulator then prints:

- the final bit
- the winning player

---

## Run tests

Execute all tests with:

```bash
./tests.sh
```

This script:

- prepares the environment
- runs Python test files from `tests/`
- shows clear logs

---

## Game flow

### 1. Join phase

Two players join the contract by sending exactly `10 tez` each and a commitment.

A commitment is a hash of:

- player address
- secret
- salt

This prevents a player from changing their secret later.

### 2. Reveal phase

Each player reveals:

- their secret
- their salt

The contract verifies that the revealed data matches the original commitment.

### 3. Initialization phase

The contract builds the initial automaton state from both secrets.

### 4. Simulation phase

The contract runs the cellular automaton in batches.

### 5. Final result

The contract extracts the final bit from the center of the final state:

- `0` → player 1 wins
- `1` → player 2 wins

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
- timeout during progress after reveal

The contract uses:

- commit-reveal
- deterministic state generation
- deterministic simulation
- timeout handling

---

## Notes

- `run.sh` is for manual interactive simulation
- `tests.sh` is for automated tests
- test parameters are intentionally smaller than a production-scale configuration to keep execution fast

---

## Main files

### `contracts/contract.py`

SmartPy contract implementing:

- join
- reveal
- batched initialization
- batched simulation
- timeout claims
- winner payout

### `contracts/simulation.py`

Python reference implementation of the same simulation logic.

### `contracts/main.py`

Interactive CLI simulator used by `run.sh`.

### `tests/test_simulation.py`

Checks the simulation logic.

### `tests/test_contract.py`

Checks the contract happy path and timeout behavior.

### `tests/test_security.py`

Checks failure cases and security scenarios.

---

## Recommended usage

For normal work:

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

Using `sudo` may:

- break `.venv` permissions
- mix user and root-owned files
- cause confusing environment issues

Preferred usage:

```bash
./create_venv.sh
./run.sh
./tests.sh
```
