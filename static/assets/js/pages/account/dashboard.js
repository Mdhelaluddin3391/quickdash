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
    // NOTE: Using specific API for customer dashboard info
    try {
        const data = await apiCall('/auth/customer/me/');
        
        // Update Address Count or other stats if available in response
        // For now, using Orders API to get count
        const orders = await apiCall('/orders/');
        document.getElementById('total-orders-count').innerText = orders.length || orders.count || 0;

        // Recent Order
        const recentOrderContainer = document.getElementById('recent-order-placeholder');
        if (orders.length > 0) {
            const last = orders[0];
            recentOrderContainer.innerHTML = `
                <div class="order-card">
                    <div class="o-info">
                        <h4>Order #${last.id.slice(0,8).toUpperCase()}</h4>
                        <p class="o-meta">${new Date(last.created_at).toLocaleDateString()} • ₹${last.final_amount}</p>
                    </div>
                    <div>
                        <span class="o-status status-${last.status.toLowerCase()}">${last.status}</span>
                        <a href="/track_order.html?id=${last.id}" class="btn-sm btn-outline ml-2">Track</a>
                    </div>
                </div>
            `;
        } else {
            recentOrderContainer.innerHTML = '<p class="text-muted">No recent orders.</p>';
        }

    } catch (e) {
        console.error("Dashboard Load Error", e);
    }
});

function logout() {
    localStorage.clear();
    window.location.href = '/auth.html';
}