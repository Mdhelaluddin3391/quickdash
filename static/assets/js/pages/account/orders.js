document.addEventListener('DOMContentLoaded', async () => {
    const list = document.getElementById('orders-list');
    
    try {
        const orders = await apiCall('/orders/');
        
        list.innerHTML = '';
        if (!orders || orders.length === 0) {
            document.getElementById('no-orders').style.display = 'block';
            return;
        }

        orders.forEach(o => {
            const date = new Date(o.created_at).toLocaleDateString();
            const statusClass = `status-${o.status.toLowerCase()}`;
            
            const div = document.createElement('div');
            div.className = 'order-card';
            div.innerHTML = `
                <div class="o-info">
                    <h4>Order #${o.id.slice(0,8).toUpperCase()}</h4>
                    <p class="o-meta">${date} • ₹${parseFloat(o.final_amount).toFixed(2)}</p>
                </div>
                <div style="display:flex; gap:10px; align-items:center;">
                    <span class="o-status ${statusClass}">${o.status}</span>
                    <a href="/track_order.html?id=${o.id}" class="btn-sm btn-outline">View</a>
                </div>
            `;
            list.appendChild(div);
        });

    } catch (e) {
        list.innerHTML = '<p class="text-danger">Failed to load orders.</p>';
    }
});