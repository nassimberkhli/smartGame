# CrowdShield 🛡️

**Decentralized Crowd Safety Prediction Market on Tezos**

CrowdShield is a community-driven prediction market that allows users to forecast crowd levels at events. A portion of all market fees automatically funds safety and prevention measures—all transparently on-chain.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Flask + JS)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Markets   │  │   Wallet    │  │     Taquito/Beacon     │  │
│  │   Pages     │  │   Connect   │  │     (Contract Calls)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Tezos Blockchain                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐   │
│  │ CrowdShieldMarket│◄─┤OracleCommitReveal│  │PreventionFund │   │
│  │                 │  │                 │  │                │   │
│  │ • create_market │  │ • register_reporter│ │ • deposit     │   │
│  │ • bet          │  │ • commit         │  │ • spend       │   │
│  │ • start_resolving│ │ • reveal         │  │               │   │
│  │ • receive_outcome│◄┤ • finalize       │  │               │   │
│  │ • claim        │  └─────────────────┘  └────────────────┘   │
│  └────────┬────────┘           │                    ▲           │
│           │                    │                    │           │
│           └────────────────────┴───── fees ─────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
Crowshield/
├── smartpy/                    # SmartPy smart contracts
│   ├── contracts/
│   │   ├── market.py          # CrowdShieldMarket contract
│   │   ├── oracle.py          # OracleCommitReveal contract
│   │   └── fund.py            # PreventionFund contract
│   └── tests/
│       └── test_all.py        # Comprehensive test suite
│
├── crowdshield/               # Python web application
│   ├── core/                  # Simulator engine (dev only)
│   │   ├── engine.py
│   │   └── models.py
│   └── web/
│       ├── app.py             # Flask application
│       ├── static/
│       │   ├── style.css      # Design system
│       │   └── tezos.js       # Taquito integration
│       └── templates/         # Jinja2 templates
│
├── tests/                     # Python tests
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Node.js (for SmartPy CLI)
- A Tezos wallet (Temple, Kukai, etc.)

### 1. Install Dependencies

```bash
# Python dependencies
python3 -m venv venv
source venv/bin/activate
pip install flask pytest

# SmartPy CLI
sh <(curl -s https://smartpy.io/cli/install.sh)
```

### 2. Run SmartPy Tests

```bash
cd smartpy
~/smartpy-cli/SmartPy.sh test tests/test_all.py output/

# View test results
open output/test_all/log.html
```

### 3. Deploy Contracts (Ghostnet)

```bash
# Compile contracts
~/smartpy-cli/SmartPy.sh compile contracts/market.py output/market/
~/smartpy-cli/SmartPy.sh compile contracts/oracle.py output/oracle/
~/smartpy-cli/SmartPy.sh compile contracts/fund.py output/fund/

# Deploy using octez-client or tezos-dapp-client
# Update addresses in:
#   - crowdshield/web/app.py (CONTRACT_CONFIG)
#   - crowdshield/web/static/tezos.js (CONFIG)
```

### 4. Run Web Application

```bash
# From project root
export PYTHONPATH=$PYTHONPATH:.
python crowdshield/web/app.py

# Open http://127.0.0.1:5000
```

## 📋 Smart Contracts

### CrowdShieldMarket

| Entrypoint | Description |
|------------|-------------|
| `create_market(question, location, threshold, end_time)` | Create new prediction market |
| `bet(market_id, side)` | Place bet on OVER or UNDER (payable) |
| `start_resolving(market_id)` | Transition to RESOLVING after deadline |
| `receive_outcome(market_id, result)` | Oracle callback to set result |
| `claim(market_id)` | Claim winnings (pull payment) |

### OracleCommitReveal

| Entrypoint | Description |
|------------|-------------|
| `register_reporter()` | Stake tez to become reporter |
| `commit(market_id, commit_hash)` | Submit hidden vote |
| `reveal(market_id, result, salt)` | Reveal vote |
| `finalize(market_id)` | Calculate result, apply slashing, callback |

### PreventionFund

| Entrypoint | Description |
|------------|-------------|
| `deposit()` | Receive fees (payable) |
| `spend(amount, recipient, description)` | Spend on safety (admin) |

## ✅ PDF Conformity Checklist

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| **Contrat A - CrowdShieldMarket** | ✅ | `smartpy/contracts/market.py` |
| Storage: admin, oracle, fee_bps, markets, bets, claimed | ✅ | Lines 52-71 |
| Types: Side, Status, Market | ✅ | Lines 17-34 |
| create_market with end_time validation | ✅ | Lines 75-103 |
| bet with OPEN/deadline/amount checks | ✅ | Lines 108-145 |
| start_resolving transition | ✅ | Lines 150-167 |
| receive_outcome oracle-only callback | ✅ | Lines 172-214 |
| claim with payout calculation | ✅ | Lines 219-276 |
| Pull payments (no loops) | ✅ | claim() pattern |
| Mutez only (no float) | ✅ | All amounts in sp.mutez |
| **Contrat B - OracleCommitReveal** | ✅ | `smartpy/contracts/oracle.py` |
| register_reporter with min_stake | ✅ | Lines 117-123 |
| commit with uniqueness check | ✅ | Lines 157-177 |
| reveal with hash verification | ✅ | Lines 182-220 |
| finalize with quorum/timeout | ✅ | Lines 225-280 |
| Slashing (absent/incorrect) | ✅ | Lines 283-293, 248-270 |
| Callback to market | ✅ | Lines 272-280 |
| **Contrat C - PreventionFund** | ✅ | `smartpy/contracts/fund.py` |
| deposit() payable | ✅ | Lines 48-52 |
| spend() admin only + journaling | ✅ | Lines 66-86 |
| **Tests SmartPy** | ✅ | `smartpy/tests/test_all.py` |
| Market unit tests | ✅ | 8 test cases |
| Oracle unit tests | ✅ | 4 test cases |
| Integration test | ✅ | Full flow test |
| **UI/Web** | ✅ | `crowdshield/web/` |
| Markets list | ✅ | `index.html` |
| Market detail + bet | ✅ | `market.html` |
| RESOLVING status | ✅ | `market.html` lines 72-92 |
| CLAIM page | ✅ | `market.html` lines 94-124 |
| Fund page | ✅ | `fund.html` |
| Wallet integration | ✅ | `tezos.js` |
| No admin resolve button | ✅ | Removed from UI |
| **Technical Requirements** | ✅ | |
| Zero critical logic off-chain | ✅ | All in SmartPy |
| Pull payments | ✅ | claim() only |
| Mutez only | ✅ | No floats |
| Anti re-resolution | ✅ | Status checks |
| Anti double-claim | ✅ | claimed big_map |
| Oracle sender check | ✅ | `sp.sender == oracle` |

## 🧪 Running Tests

### SmartPy Tests
```bash
cd smartpy
~/smartpy-cli/SmartPy.sh test tests/test_all.py output/
```

### Python Tests (Simulator)
```bash
pytest tests/
```

## 🔐 Security Notes

1. **Oracle Trust**: The commit-reveal oracle requires trusted reporters. Consider using a DAO or multi-sig for reporter management.

2. **Slashing**: Current slashing percentages (10% absent, 30% wrong) are configurable at deployment.

3. **Admin Keys**: Secure the admin keys for PreventionFund spend operations.

4. **Front-running**: Commit-reveal pattern protects against front-running oracle votes.

## 📜 License

MIT License - See LICENSE file for details.

## 🤝 Contributing

Contributions welcome! Please read CONTRIBUTING.md for guidelines.
