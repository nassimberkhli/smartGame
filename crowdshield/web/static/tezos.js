/**
 * CrowdShield Tezos Integration
 * Wallet connection and contract interaction using Taquito + Beacon
 */

// Configuration - Update these after deploying contracts to testnet/mainnet
const CONFIG = {
    network: 'ghostnet', // or 'mainnet'
    rpcUrl: 'https://ghostnet.ecadinfra.com',
    // Contract addresses - UPDATE AFTER DEPLOYMENT
    marketContract: '', // CrowdShieldMarket address
    oracleContract: '', // OracleCommitReveal address
    fundContract: '',   // PreventionFund address
};

// State
let wallet = null;
let tezos = null;
let userAddress = null;
let marketContract = null;
let fundContract = null;

/**
 * Initialize Taquito with Beacon wallet
 */
async function initTezos() {
    // Create Beacon wallet instance
    wallet = new beacon.DAppClient({
        name: 'CrowdShield',
        preferredNetwork: CONFIG.network === 'mainnet'
            ? beacon.NetworkType.MAINNET
            : beacon.NetworkType.GHOSTNET,
    });

    // Create Taquito instance
    tezos = new taquito.TezosToolkit(CONFIG.rpcUrl);
    tezos.setWalletProvider(wallet);

    // Check if already connected
    const activeAccount = await wallet.getActiveAccount();
    if (activeAccount) {
        userAddress = activeAccount.address;
        updateWalletUI();
        await initContracts();
    }
}

/**
 * Connect wallet
 */
async function connectWallet() {
    try {
        const permissions = await wallet.requestPermissions({
            network: {
                type: CONFIG.network === 'mainnet'
                    ? beacon.NetworkType.MAINNET
                    : beacon.NetworkType.GHOSTNET,
            },
        });
        userAddress = permissions.address;
        updateWalletUI();
        await initContracts();
        showNotification('Wallet connected!', 'success');
    } catch (error) {
        console.error('Wallet connection failed:', error);
        showNotification('Failed to connect wallet', 'error');
    }
}

/**
 * Disconnect wallet
 */
async function disconnectWallet() {
    await wallet.clearActiveAccount();
    userAddress = null;
    marketContract = null;
    fundContract = null;
    updateWalletUI();
    showNotification('Wallet disconnected', 'info');
}

/**
 * Update wallet UI elements
 */
function updateWalletUI() {
    const connectBtn = document.getElementById('wallet-connect-btn');
    const addressDisplay = document.getElementById('wallet-address');
    const walletActions = document.getElementById('wallet-actions');

    if (userAddress) {
        if (connectBtn) connectBtn.style.display = 'none';
        if (addressDisplay) {
            addressDisplay.textContent = formatAddress(userAddress);
            addressDisplay.style.display = 'inline-block';
        }
        if (walletActions) walletActions.style.display = 'flex';
    } else {
        if (connectBtn) connectBtn.style.display = 'inline-block';
        if (addressDisplay) addressDisplay.style.display = 'none';
        if (walletActions) walletActions.style.display = 'none';
    }
}

/**
 * Format address for display (tz1...abc)
 */
function formatAddress(address) {
    if (!address) return '';
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

/**
 * Initialize contract instances
 */
async function initContracts() {
    if (!CONFIG.marketContract || !CONFIG.fundContract) {
        console.warn('Contract addresses not configured');
        return;
    }

    try {
        marketContract = await tezos.wallet.at(CONFIG.marketContract);
        fundContract = await tezos.wallet.at(CONFIG.fundContract);
    } catch (error) {
        console.error('Failed to initialize contracts:', error);
    }
}

/**
 * Place a bet on a market
 * @param {number} marketId - Market ID
 * @param {string} side - 'OVER' or 'UNDER'
 * @param {number} amount - Amount in tez
 */
async function placeBet(marketId, side, amount) {
    if (!userAddress) {
        showNotification('Please connect your wallet first', 'warning');
        return;
    }

    if (!marketContract) {
        showNotification('Contract not initialized', 'error');
        return;
    }

    try {
        showLoading(true);

        // Convert side to Michelson variant
        const sideVariant = side === 'OVER' ? { OVER: null } : { UNDER: null };

        const op = await marketContract.methods
            .bet(marketId, sideVariant)
            .send({ amount: amount, mutez: false });

        showNotification('Transaction submitted. Waiting for confirmation...', 'info');

        await op.confirmation(1);

        showNotification(`Bet placed successfully! ${amount} ꜩ on ${side}`, 'success');

        // Reload page to show updated state
        setTimeout(() => location.reload(), 2000);

    } catch (error) {
        console.error('Bet failed:', error);
        showNotification(`Bet failed: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
}

/**
 * Claim winnings from a resolved market
 * @param {number} marketId - Market ID
 */
async function claimWinnings(marketId) {
    if (!userAddress) {
        showNotification('Please connect your wallet first', 'warning');
        return;
    }

    if (!marketContract) {
        showNotification('Contract not initialized', 'error');
        return;
    }

    try {
        showLoading(true);

        const op = await marketContract.methods
            .claim(marketId)
            .send();

        showNotification('Claim submitted. Waiting for confirmation...', 'info');

        await op.confirmation(1);

        showNotification('Winnings claimed successfully!', 'success');

        setTimeout(() => location.reload(), 2000);

    } catch (error) {
        console.error('Claim failed:', error);

        // Handle specific errors
        if (error.message.includes('ALREADY_CLAIMED')) {
            showNotification('You have already claimed for this market', 'warning');
        } else if (error.message.includes('NO_WINNING_BET')) {
            showNotification('You did not have a winning bet', 'warning');
        } else {
            showNotification(`Claim failed: ${error.message}`, 'error');
        }
    } finally {
        showLoading(false);
    }
}

/**
 * Start resolution process for a market
 * @param {number} marketId - Market ID
 */
async function startResolving(marketId) {
    if (!userAddress) {
        showNotification('Please connect your wallet first', 'warning');
        return;
    }

    if (!marketContract) {
        showNotification('Contract not initialized', 'error');
        return;
    }

    try {
        showLoading(true);

        const op = await marketContract.methods
            .start_resolving(marketId)
            .send();

        showNotification('Resolution started. Waiting for confirmation...', 'info');

        await op.confirmation(1);

        showNotification('Market is now in RESOLVING state. Oracle will determine outcome.', 'success');

        setTimeout(() => location.reload(), 2000);

    } catch (error) {
        console.error('Start resolving failed:', error);
        showNotification(`Failed to start resolution: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
}

/**
 * Get market data from contract view
 * @param {number} marketId - Market ID
 */
async function getMarketData(marketId) {
    if (!marketContract) return null;

    try {
        const storage = await marketContract.storage();
        const market = await storage.markets.get(marketId);
        return market;
    } catch (error) {
        console.error('Failed to get market data:', error);
        return null;
    }
}

/**
 * Get user's bet for a market
 * @param {number} marketId - Market ID
 * @param {string} side - 'OVER' or 'UNDER'
 */
async function getUserBet(marketId, side) {
    if (!marketContract || !userAddress) return 0;

    try {
        const storage = await marketContract.storage();
        const sideKey = side === 'OVER' ? { OVER: null } : { UNDER: null };
        const bet = await storage.bets.get([marketId, userAddress, sideKey]);
        return bet ? bet.toNumber() / 1000000 : 0; // Convert mutez to tez
    } catch (error) {
        console.error('Failed to get user bet:', error);
        return 0;
    }
}

/**
 * Get fund statistics
 */
async function getFundStats() {
    if (!fundContract) return null;

    try {
        const storage = await fundContract.storage();
        return {
            balance: storage.balance ? storage.balance.toNumber() / 1000000 : 0,
            totalReceived: storage.total_received ? storage.total_received.toNumber() / 1000000 : 0,
            totalSpent: storage.total_spent ? storage.total_spent.toNumber() / 1000000 : 0,
        };
    } catch (error) {
        console.error('Failed to get fund stats:', error);
        return null;
    }
}

/**
 * Show notification toast
 */
function showNotification(message, type = 'info') {
    const container = document.getElementById('notification-container') || createNotificationContainer();

    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <span class="notification-message">${message}</span>
        <button class="notification-close" onclick="this.parentElement.remove()">×</button>
    `;

    container.appendChild(notification);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

/**
 * Create notification container if it doesn't exist
 */
function createNotificationContainer() {
    const container = document.createElement('div');
    container.id = 'notification-container';
    document.body.appendChild(container);
    return container;
}

/**
 * Show/hide loading overlay
 */
function showLoading(show) {
    let overlay = document.getElementById('loading-overlay');

    if (!overlay && show) {
        overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.innerHTML = `
            <div class="loading-spinner"></div>
            <p>Processing transaction...</p>
        `;
        document.body.appendChild(overlay);
    }

    if (overlay) {
        overlay.style.display = show ? 'flex' : 'none';
    }
}

/**
 * Format mutez to tez display
 */
function formatTez(mutez) {
    const tez = mutez / 1000000;
    return `${tez.toLocaleString()} ꜩ`;
}

/**
 * Format timestamp to readable date
 */
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    await initTezos();

    // Attach event listeners
    const connectBtn = document.getElementById('wallet-connect-btn');
    if (connectBtn) {
        connectBtn.addEventListener('click', connectWallet);
    }

    const disconnectBtn = document.getElementById('wallet-disconnect-btn');
    if (disconnectBtn) {
        disconnectBtn.addEventListener('click', disconnectWallet);
    }

    // Handle bet form submission
    const betForm = document.getElementById('bet-form');
    if (betForm) {
        betForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const marketId = parseInt(betForm.dataset.marketId);
            const side = betForm.querySelector('input[name="side"]:checked').value;
            const amount = parseFloat(betForm.querySelector('input[name="amount"]').value);
            await placeBet(marketId, side, amount);
        });
    }

    // Handle claim button
    const claimBtn = document.getElementById('claim-btn');
    if (claimBtn) {
        claimBtn.addEventListener('click', async () => {
            const marketId = parseInt(claimBtn.dataset.marketId);
            await claimWinnings(marketId);
        });
    }

    // Handle start resolving button
    const resolveBtn = document.getElementById('start-resolving-btn');
    if (resolveBtn) {
        resolveBtn.addEventListener('click', async () => {
            const marketId = parseInt(resolveBtn.dataset.marketId);
            await startResolving(marketId);
        });
    }
});
