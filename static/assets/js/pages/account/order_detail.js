let currentOrderId = null;

document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    currentOrderId = params.get('id');

    if (!currentOrderId) {
        window.location.href = '/orders.html';
        return;
    }

    try {
        const order = await apiCall(`/orders/${currentOrderId}/`);
        renderOrderDetail(order);
    } catch (e) {
        document.getElementById('od-loader').innerHTML = `<p class="text-danger">Error: ${e.message}</p>`;
    }
});

function renderOrderDetail(order) {
    document.getElementById('od-loader').style.display = 'none';
    document.getElementById('od-container').style.display = 'block';

    // Header
    document.getElementById('disp-id').innerText = `Order #${order.id.slice(0, 8).toUpperCase()}`;
    document.getElementById('disp-date').innerText = new Date(order.created_at).toLocaleString();
    
    // Status Badge
    const statusMap = {
        'pending': 'badge-pending',
        'confirmed': 'badge-confirmed',
        'delivered': 'badge-delivered',
        'cancelled': 'badge-cancelled'
    };
    const badgeClass = statusMap[order.status.toLowerCase()] || 'badge-pending';
    document.getElementById('disp-status').innerHTML = `<span class="od-status-badge ${badgeClass}">${order.status}</span>`;

    // Items
    const itemsList = document.getElementById('items-list');
    itemsList.innerHTML = order.items.map(item => `
        <div class="item-row">
            <img src="${item.sku_image || 'https://via.placeholder.com/60'}" class="item-img">
            <div class="item-details">
                <h4>${item.sku_name_snapshot}</h4>
                <div class="text-muted text-sm">Qty: ${item.quantity} x ₹${item.unit_price}</div>
            </div>
            <div class="item-price">₹${item.total_price}</div>
        </div>
    `).join('');

    // Summary
    document.getElementById('val-sub').innerText = `₹${order.total_amount}`;
    document.getElementById('val-del').innerText = `₹${order.delivery_fee}`;
    document.getElementById('val-disc').innerText = `-₹${order.discount_amount}`;
    document.getElementById('val-total').innerText = `₹${order.final_amount}`;

    // Address
    if(order.delivery_address_json) {
        const a = order.delivery_address_json;
        document.getElementById('disp-addr').innerText = `${a.full_address}, ${a.city} - ${a.pincode}`;
    }

    // Actions
    document.getElementById('btn-track').href = `/track_order.html?id=${order.id}`;
    
    if (['pending', 'confirmed'].includes(order.status.toLowerCase())) {
        document.getElementById('btn-cancel').style.display = 'block';
    }
}

async function cancelCurrentOrder() {
    if(!confirm("Are you sure you want to cancel this order?")) return;
    
    try {
        await apiCall(`/orders/${currentOrderId}/cancel/`, 'POST', { reason: "User cancelled from web" });
        alert("Order Cancelled");
        window.location.reload();
    } catch (e) {
        alert(e.message);
    }
}