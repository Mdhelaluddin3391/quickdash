// Dashboard State Management
let allOrders = [];
const recentOrdersCount = 5;  // Show only 5 recent orders on dashboard

document.addEventListener('DOMContentLoaded', async () => {
    // Auth Check
    if (!APP_CONFIG.IS_LOGGED_IN) {
        window.location.href = '/auth.html';
        return;
    }

    // 1. Populate Sidebar Info
    const user = APP_CONFIG.USER;
    if (user) {
        document.getElementById('nav-name').innerText = user.full_name || "User";
        document.getElementById('nav-phone').innerText = user.phone;
        document.getElementById('nav-avatar').innerText = (user.full_name || "U").charAt(0).toUpperCase();
    }

    // 2. Fetch Dashboard Data
    try {
        await loadDashboardData();
    } catch (e) {
        console.error("Dashboard Load Error", e);
        showError("Failed to load dashboard", 3000);
    }
});

async function loadDashboardData() {
    try {
        // Fetch all orders for current user
        const ordersResp = await apiCall('/orders/', 'GET', null, true);
        allOrders = Array.isArray(ordersResp) ? ordersResp : (ordersResp.results || []);
        
        // Sort orders by date (newest first)
        allOrders.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

        // Calculate Statistics
        calculateStatistics();

        // Display first page of orders
        currentPage = 1;
        displayOrders();

    } catch (e) {
        console.error("Orders Load Error", e);
        showError("Failed to load orders", 3000);
    }
}

function calculateStatistics() {
    const totalCount = allOrders.length;
    
    let totalSpent = 0;
    let totalSaved = 0;

    allOrders.forEach(order => {
        // Total spent = final amount paid
        totalSpent += parseFloat(order.final_amount || 0);
        
        // Calculate saved = original price - sale price
        if (order.items && Array.isArray(order.items)) {
            order.items.forEach(item => {
                const originalPrice = parseFloat(item.original_price || item.sale_price || 0);
                const salePrice = parseFloat(item.sale_price || 0);
                const saved = originalPrice - salePrice;
                if (saved > 0) {
                    totalSaved += saved * (item.quantity || 1);
                }
            });
        }
    });

    // Update DOM
    document.getElementById('total-orders-count').innerText = totalCount;
    document.getElementById('total-spent').innerText = `₹${totalSpent.toFixed(2)}`;
    document.getElementById('total-saved').innerText = `₹${totalSaved.toFixed(2)}`;
}

function displayOrders() {
    const container = document.getElementById('recent-orders-container');
    const emptyState = document.getElementById('empty-orders-state');

    // Handle empty state
    if (allOrders.length === 0) {
        container.innerHTML = '';
        emptyState.style.display = 'block';
        return;
    }

    emptyState.style.display = 'none';

    // Show only 5 recent orders on dashboard (no pagination)
    const recentOrders = allOrders.slice(0, recentOrdersCount);

    // Render recent orders
    container.innerHTML = '';
    recentOrders.forEach(order => {
        const orderCard = createOrderCard(order);
        container.appendChild(orderCard);
    });
}

function createOrderCard(order) {
    const div = document.createElement('div');
    div.className = 'order-card';
    
    const date = new Date(order.created_at).toLocaleDateString('en-IN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
    
    const statusClass = `status-${order.status.toLowerCase()}`;
    const statusText = order.status.charAt(0).toUpperCase() + order.status.slice(1);
    const orderId = order.id.slice(0, 8).toUpperCase();
    const amount = parseFloat(order.final_amount).toFixed(2);

    // Count items in order
    const itemCount = order.items ? order.items.reduce((sum, item) => sum + (item.quantity || 1), 0) : 0;

    div.innerHTML = `
        <div class="o-info">
            <h4>Order #${orderId}</h4>
            <p class="o-meta">${date} • ${itemCount} item${itemCount !== 1 ? 's' : ''} • ₹${amount}</p>
        </div>
        <div style="display:flex; gap:10px; align-items:center;">
            <span class="o-status ${statusClass}">${statusText}</span>
            <a href="/track_order.html?id=${order.id}" class="btn-sm btn-outline">Track</a>
        </div>
    `;
    
    return div;
}

function logout() {
    localStorage.clear();
    window.location.href = '/auth.html';
}