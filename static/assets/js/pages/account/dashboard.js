// static/assets/js/pages/account/dashboard.js

let allOrders = [];
const recentOrdersCount = 5;

document.addEventListener('DOMContentLoaded', async () => {
    // Auth Check
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/auth.html';
        return;
    }

    // 1. Populate Sidebar Info
    const userStr = localStorage.getItem('user');
    if (userStr) {
        const user = JSON.parse(userStr);
        if(document.getElementById('nav-name')) document.getElementById('nav-name').innerText = user.full_name || "User";
        if(document.getElementById('nav-phone')) document.getElementById('nav-phone').innerText = user.phone;
        if(document.getElementById('nav-avatar')) document.getElementById('nav-avatar').innerText = (user.full_name || "U").charAt(0).toUpperCase();
    }

    // 2. Fetch Dashboard Data
    try {
        await loadDashboardData();
    } catch (e) {
        console.error("Dashboard Load Error", e);
        // Don't show error alert immediately on dashboard to avoid annoyance
    }
});

async function loadDashboardData() {
    try {
        // Endpoint: /api/v1/orders/
        const ordersResp = await apiCall('/orders/', 'GET', null, true);
        allOrders = Array.isArray(ordersResp) ? ordersResp : (ordersResp.results || []);
        
        // Sort orders by date (newest first)
        allOrders.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

        calculateStatistics();
        displayOrders();

    } catch (e) {
        console.error("Orders Load Error", e);
        throw e;
    }
}

function calculateStatistics() {
    const totalCount = allOrders.length;
    let totalSpent = 0;

    allOrders.forEach(order => {
        totalSpent += parseFloat(order.final_amount || 0);
    });

    if(document.getElementById('total-orders-count')) document.getElementById('total-orders-count').innerText = totalCount;
    if(document.getElementById('total-spent')) document.getElementById('total-spent').innerText = `₹${totalSpent.toFixed(2)}`;
}

function displayOrders() {
    const container = document.getElementById('recent-orders-container');
    const emptyState = document.getElementById('empty-orders-state');

    if (!container) return;

    // Handle empty state
    if (allOrders.length === 0) {
        container.innerHTML = '';
        if(emptyState) emptyState.style.display = 'block';
        return;
    }

    if(emptyState) emptyState.style.display = 'none';

    // Show recent orders
    const recentOrders = allOrders.slice(0, recentOrdersCount);

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
    
    const statusClass = `status-${(order.status || 'pending').toLowerCase()}`;
    const statusText = (order.status || 'Pending').charAt(0).toUpperCase() + (order.status || 'pending').slice(1);
    const orderId = order.id ? order.id.slice(0, 8).toUpperCase() : '---';
    const amount = parseFloat(order.final_amount || 0).toFixed(2);

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

window.logout = function() {
    localStorage.clear();
    window.location.href = '/auth.html';
}