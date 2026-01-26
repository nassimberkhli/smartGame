"""
CrowdShield Web Application

Flask-based web UI for the CrowdShield prediction market dApp.
This serves as a frontend that interacts with Tezos smart contracts via Taquito.

The Python engine is kept as a SIMULATOR for development/testing only.
In production, all state comes from the blockchain.
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import datetime
from crowdshield.core.engine import CrowdShieldEngine
from crowdshield.core.models import BetSide, MarketStatus

app = Flask(__name__)
app.secret_key = 'crowdshield-secret-key-change-in-production'

# =============================================================================
# Configuration
# =============================================================================

# Contract addresses on Ghostnet (UPDATE AFTER DEPLOYMENT)
CONTRACT_CONFIG = {
    'network': 'ghostnet',
    'rpc_url': 'https://ghostnet.ecadinfra.com',
    'market_contract': '',   # CrowdShieldMarket address
    'oracle_contract': '',   # OracleCommitReveal address  
    'fund_contract': '',     # PreventionFund address
}

# =============================================================================
# Simulator Engine (Development Only)
# =============================================================================
# This engine is used for local development/testing without blockchain.
# In production, all reads come from Tezos contract storage.

engine = CrowdShieldEngine()

# =============================================================================
# Template Filters
# =============================================================================

@app.template_filter('tez')
def tez_filter(value):
    """Format value as tez."""
    return f"{value:.2f}"

# =============================================================================
# API Endpoints
# =============================================================================

@app.route('/api/config')
def get_config():
    """Return contract configuration for frontend."""
    return jsonify(CONTRACT_CONFIG)

# =============================================================================
# Page Routes
# =============================================================================

@app.route('/')
def index():
    """Home page - list all markets."""
    markets = engine.get_all_markets()
    return render_template('index.html', markets=markets)


@app.route('/create', methods=['GET', 'POST'])
def create_market():
    """Create a new market."""
    if request.method == 'POST':
        question = request.form['question']
        location = request.form['location']
        threshold = request.form['threshold']
        
        # Parse end_time from form
        end_time_str = request.form.get('end_time')
        if end_time_str:
            try:
                end_time = datetime.datetime.fromisoformat(end_time_str)
            except ValueError:
                end_time = datetime.datetime.now() + datetime.timedelta(days=1)
        else:
            end_time = datetime.datetime.now() + datetime.timedelta(days=1)
        
        start_time = datetime.datetime.now()
        
        # Create market in simulator
        engine.create_market(question, location, threshold, start_time, end_time)
        flash('Market created successfully! In production, this would be on-chain.')
        return redirect(url_for('index'))
    
    return render_template('create.html')


@app.route('/market/<market_id>', methods=['GET', 'POST'])
def market_detail(market_id):
    """Market detail page with betting."""
    market = engine.get_market(market_id)
    
    if not market:
        return "Market not found", 404
    
    # Handle simulator bets (for development only)
    if request.method == 'POST' and 'side' in request.form:
        side_str = request.form['side']
        amount = float(request.form.get('amount', 10))
        side = BetSide.OVER if side_str == 'OVER' else BetSide.UNDER
        
        # Get or create demo user
        user = engine.get_user("demo_user")
        if not user:
            user = engine.create_user("demo_user", "Demo User")
        
        try:
            engine.place_bet(user.id, market.id, side, amount)
            flash(f'Bet placed: {amount} ꜩ on {side.value} (Simulator)')
        except ValueError as e:
            flash(str(e), 'error')
        
        return redirect(url_for('market_detail', market_id=market_id))
    
    return render_template('market.html', market=market)


@app.route('/fund')
def fund_dashboard():
    """Prevention Fund dashboard."""
    return render_template('fund.html', fund=engine.fund)


# =============================================================================
# Development/Testing Routes (Remove in Production)
# =============================================================================

@app.route('/dev/resolve/<market_id>', methods=['POST'])
def dev_resolve(market_id):
    """
    Development endpoint to simulate market resolution.
    In production, this is handled by the Oracle contract.
    """
    result_str = request.form.get('result', 'OVER')
    result = BetSide.OVER if result_str == 'OVER' else BetSide.UNDER
    
    market = engine.get_market(market_id)
    if market:
        engine.resolve_market(market_id, result)
        flash(f'Market resolved as {result.value} (Simulator)')
    
    return redirect(url_for('market_detail', market_id=market_id))


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    print("""
    ╔═══════════════════════════════════════════════════════════════════╗
    ║                     CrowdShield dApp                              ║
    ╠═══════════════════════════════════════════════════════════════════╣
    ║  Running in DEVELOPMENT MODE                                       ║
    ║  Using Python simulator - NOT connected to blockchain              ║
    ║                                                                    ║
    ║  To connect to Tezos:                                              ║
    ║  1. Deploy contracts to Ghostnet                                   ║
    ║  2. Update CONTRACT_CONFIG in app.py                               ║
    ║  3. Update CONFIG in static/tezos.js                               ║
    ╚═══════════════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, port=5000)
