// static/assets/js/pages/checkout/cart.js

document.addEventListener('DOMContentLoaded', async () => {
    // FIX: Standard Auth Check
    if (!localStorage.getItem('access_token')) {
        window.location.href = '/auth.html';
        return;
    }

    loadCart();
});

async function loadCart() {
    const loader = document.getElementById('cart-loader');
    const content = document.getElementById('cart-content');
    const emptyState = document.getElementById('empty-cart');

    try {
        const cart = await apiCall('/orders/cart/');
        
        loader.style.display = 'none';

        if (!cart.items || cart.items.length === 0) {
            emptyState.style.display = 'block';
            content.style.display = 'none';
            return;
        }

        content.style.display = 'flex'; 
        renderCartItems(cart.items);
        renderSummary(cart);

    } catch (error) {
        console.error("Cart error:", error);
        loader.innerHTML = `<p style="color:red">Failed to load cart. Refresh page.</p>`;
    }
}

function renderCartItems(items) {
    const list = document.getElementById('cart-items-list');
    list.innerHTML = items.map(item => `
        <div class="cart-item-card">
            <img src="${item.sku_image || 'https://via.placeholder.com/80'}" class="c-img">
            <div class="c-info">
                <div class="c-name">${item.sku_name}</div>
                <div class="c-unit">Unit Price: ₹${item.price}</div>
                <div class="c-price mt-1">₹${item.total_price}</div>
            </div>
            <div class="c-qty">
                <button class="btn-qty" onclick="updateQty('${item.sku_id}', ${item.quantity - 1})">-</button>
                <span>${item.quantity}</span>
                <button class="btn-qty" onclick="updateQty('${item.sku_id}', ${item.quantity + 1})">+</button>
            </div>
        </div>
    `).join('');
    
    // Update Badge
    const badge = document.getElementById('cart-count-badge');
    if(badge) badge.innerText = `(${items.length})`;
}

function renderSummary(cart) {
    const subtotal = parseFloat(cart.total_amount);
    const fee = 20; // Delivery Fee
    const total = subtotal + fee;

    document.getElementById('subtotal').innerText = `₹${subtotal.toFixed(2)}`;
    document.getElementById('delivery-fee').innerText = `₹${fee}`;
    document.getElementById('final-total').innerText = `₹${total.toFixed(2)}`;
}

async function updateQty(skuId, newQty) {
    try {
        await apiCall('/orders/cart/add/', 'POST', { sku_id: skuId, quantity: newQty });
        loadCart(); 
        if(window.updateGlobalCartCount) window.updateGlobalCartCount();
    } catch (e) {
        alert(e.message || "Failed to update");
    }
}