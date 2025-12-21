// static/assets/js/pages/checkout/cart.js

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Auth Check using Central Config
    if (window.APP_CONFIG && !window.APP_CONFIG.IS_LOGGED_IN) {
        // Redirect to Login if not authenticated
        const loginUrl = window.APP_CONFIG.URLS ? window.APP_CONFIG.URLS.LOGIN : '/auth.html';
        window.location.href = loginUrl;
        return;
    }

    // 2. Load Data
    await loadCart();
});

async function loadCart() {
    const loader = document.getElementById('cart-loader');
    const content = document.getElementById('cart-content');
    const emptyState = document.getElementById('empty-cart');

    try {
        const cart = await apiCall('/orders/cart/', 'GET', null, true);
        
        if (loader) loader.style.display = 'none';

        if (!cart.items || cart.items.length === 0) {
            if(emptyState) emptyState.style.display = 'block';
            if(content) content.style.display = 'none';
            
            // Sync zero count
            if(window.updateGlobalCartCount) window.updateGlobalCartCount();
            return;
        }

        if(content) content.style.display = 'flex';
        if(emptyState) emptyState.style.display = 'none';
        
        renderCartItems(cart.items);
        renderSummary(cart);
        
        // Sync actual count
        if(window.updateGlobalCartCount) window.updateGlobalCartCount();

    } catch (error) {
        console.error("Cart error:", error);
        if(loader) loader.innerHTML = `<p class="text-danger text-center mt-3">Failed to load cart. <br> <button class="btn btn-sm btn-outline-primary mt-2" onclick="location.reload()">Retry</button></p>`;
    }
}

function renderCartItems(items) {
    const list = document.getElementById('cart-items-list');
    if(!list) return;

    list.innerHTML = items.map(item => `
        <div class="cart-item-card">
            <img src="${item.sku_image || '/static/assets/img/placeholder.png'}" 
                 class="c-img" 
                 onerror="this.src='/static/assets/img/placeholder.png'">
            <div class="c-info">
                <div class="c-name">${item.sku_name || 'Product'}</div>
                <div class="c-unit text-muted small">Unit Price: ₹${item.price}</div>
                <div class="c-price mt-1">₹${item.total_price}</div>
            </div>
            <div class="c-qty">
                <button class="btn-qty" 
                        onclick="updateQty('${item.sku_id}', ${item.quantity - 1})"
                        ${item.quantity <= 1 ? '' : ''}>-</button>
                <span>${item.quantity}</span>
                <button class="btn-qty" 
                        onclick="updateQty('${item.sku_id}', ${item.quantity + 1})">+</button>
            </div>
        </div>
    `).join('');
    
    // Update Local Page Badge
    const badge = document.getElementById('cart-count-badge');
    if(badge) badge.innerText = `(${items.length})`;
}

function renderSummary(cart) {
    const subtotal = parseFloat(cart.total_amount || 0);
    const fee = 20; // TODO: Fetch from backend config if possible
    const total = subtotal + fee;

    const elSub = document.getElementById('subtotal');
    const elFee = document.getElementById('delivery-fee');
    const elTotal = document.getElementById('final-total');

    if(elSub) elSub.innerText = `₹${subtotal.toFixed(2)}`;
    if(elFee) elFee.innerText = `₹${fee.toFixed(2)}`;
    if(elTotal) elTotal.innerText = `₹${total.toFixed(2)}`;
}

async function updateQty(skuId, newQty) {
    if (newQty < 0) return;

    try {
        // If qty is 0, backend usually handles it as remove, or we call delete.
        // Assuming /add/ handles updates:
        await apiCall('/orders/cart/add/', 'POST', { sku_id: skuId, quantity: newQty }, true);
        
        // Refresh cart UI
        await loadCart();
        
        if (window.showToast) window.showToast("Cart updated", "success");

    } catch (e) {
        console.error("Update failed", e);
        const msg = e.detail || e.message || "Failed to update quantity";
        
        if (window.showToast) window.showToast(msg, "error");
        else alert(msg);
    }
}

// Expose updateQty to window for HTML onclick access
window.updateQty = updateQty;