// assets/js/profile.js

document.addEventListener('DOMContentLoaded', async () => {
    if (!isLoggedIn()) window.location.href = 'auth.html';

    // Load Profile Info
    const userStr = localStorage.getItem('user');
    if(userStr) {
        const user = JSON.parse(userStr);
        document.querySelector('.user-name').innerText = user.full_name || "User";
        document.querySelector('.user-phone').innerText = user.phone;
    }

    // Load Orders
    loadOrders();

    // Logout
    document.querySelector('.logout-link').addEventListener('click', (e) => {
        e.preventDefault();
        logout();
    });
});

async function loadOrders() {
    const container = document.getElementById('orders');
    // Clear static content
    container.innerHTML = '<h2 class="content-title">Order History</h2>';

    try {
        const orders = await apiCall('/orders/', 'GET', null, true);

        orders.forEach(order => {
            const div = document.createElement('div');
            div.className = `order-card ${order.status}`; // Status class for styling
            div.innerHTML = `
                <div class="order-header">
                    <span class="order-id">Order #${order.id.slice(0,8).toUpperCase()}</span>
                    <span class="order-status">${order.status}</span>
                </div>
                <div class="order-details">
                    <p><strong>Total:</strong> ₹${order.final_amount}</p>
                    <p><strong>Date:</strong> ${new Date(order.created_at).toLocaleDateString()}</p>
                </div>
                <div class="order-actions">
                    <a href="track_order.html?id=${order.id}" class="btn btn-primary">Track</a>
                </div>
            `;
            container.appendChild(div);
        });

    } catch (e) {
        container.innerHTML += '<p>No orders found.</p>';
    }
}