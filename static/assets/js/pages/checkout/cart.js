document.addEventListener('DOMContentLoaded', async () => {
    // Check Auth
    if (!APP_CONFIG.IS_LOGGED_IN) {
        window.location.href = '/auth.html?next=/cart.html';
        return;
    }

    loadCart();
});

async function loadCart() {
    const loader = document.getElementById('cart-loader');
    const content = document.getElementById('cart-content');
    const emptyState = document.getElementById('empty-cart');
    const list = document.getElementById('cart-items-list');

    try {
        const cart = await apiCall('/orders/cart/');
        
        loader.style.display = 'none';

        if (!cart.items || cart.items.length === 0) {
            emptyState.style.display = 'block';
            content.style.display = 'none';
            return;
        }

        content.style.display = 'flex'; // Restore grid
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
                <btn onclick="updateQty('${item.sku_id}', ${item.quantity - 1})">-</btn>
                <span>${item.quantity}</span>
                <btn onclick="updateQty('${item.sku_id}', ${item.quantity + 1})">+</btn>
            </div>
        </div>
    `).join('');
    
    // Update Badge
    document.getElementById('cart-count-badge').innerText = `(${items.length})`;
}

function renderSummary(cart) {
    const subtotal = parseFloat(cart.total_amount);
    // Hardcoded for now, ideal to fetch from /utils/config/
    const fee = 20; 
    const total = subtotal + fee;

    document.getElementById('subtotal').innerText = `₹${subtotal.toFixed(2)}`;
    document.getElementById('delivery-fee').innerText = `₹${fee}`;
    document.getElementById('final-total').innerText = `₹${total.toFixed(2)}`;
}

async function updateQty(skuId, newQty) {
    try {
        // Optimistic UI update could be done here, but simple reload is safer for syncing
        await apiCall('/orders/cart/add/', 'POST', { sku_id: skuId, quantity: newQty });
        loadCart(); // Reload to get fresh calculations
        if(window.updateGlobalCartCount) window.updateGlobalCartCount();
    } catch (e) {
        alert(e.message || "Failed to update");
    }
}