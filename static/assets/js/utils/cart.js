// assets/js/utils/cart.js

document.addEventListener('DOMContentLoaded', loadCart);

// Global settings fetch karne ke liye helper function
async function fetchGlobalSettings() {
    try {
        const config = await apiCall('/utils/config/', 'GET');
        return parseFloat(config.base_delivery_fee);
    } catch (error) {
        console.warn("Delivery fee fetch failed, using fallback value.", error);
        return 20.00;
    }
}

async function loadCart() {
    const listContainer = document.querySelector('.cart-items-list');
    const emptyMsg = document.querySelector('.empty-cart-message');
    const summaryContainer = document.querySelector('.order-summary-container');

    // --- FIX: Auth check with Redirect ---
    if (!isLoggedIn()) {
        // Current page (Cart) ko yaad rakhne ke liye query param add kiya
        window.location.href = 'auth.html?next=cart.html';
        return;
    }

    try {
        const [cart, deliveryFee] = await Promise.all([
            apiCall('/orders/cart/', 'GET', null, true),
            fetchGlobalSettings()
        ]);

        if (!cart.items || cart.items.length === 0) {
            if(emptyMsg) emptyMsg.style.display = 'block';
            if(summaryContainer) summaryContainer.style.display = 'none';
            const oldItems = document.querySelectorAll('.cart-item');
            oldItems.forEach(el => el.remove());
            return;
        }

        if(emptyMsg) emptyMsg.style.display = 'none';
        if(summaryContainer) summaryContainer.style.display = 'block';

        const existingItems = document.querySelectorAll('.cart-item');
        existingItems.forEach(e => e.remove());

        const header = document.querySelector('.cart-header');

        cart.items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'cart-item';
            const imgSrc = item.sku_image || 'https://via.placeholder.com/100?text=No+Image';

            div.innerHTML = `
                <img src="${imgSrc}" class="item-image" alt="${item.sku_name}">
                <div class="item-details">
                    <h3 class="item-name">${item.sku_name}</h3>
                    <p class="item-price-per-unit">₹${parseFloat(item.price).toFixed(2)}</p>
                </div>
                <div class="item-controls">
                    <div class="item-quantity-control">
                        <button class="quantity-btn" onclick="updateQty('${item.sku_id}', ${item.quantity - 1})">
                            <i class="fas fa-minus"></i>
                        </button>
                        <span class="quantity-value">${item.quantity}</span>
                        <button class="quantity-btn" onclick="updateQty('${item.sku_id}', ${item.quantity + 1})">
                            <i class="fas fa-plus"></i>
                        </button>
                    </div>
                    <div class="item-total-price">₹${parseFloat(item.total_price).toFixed(2)}</div>
                </div>
            `;
            if(header && header.parentNode) {
                header.parentNode.insertBefore(div, header.nextSibling);
            }
        });

        const subTotal = parseFloat(cart.total_amount);
        const finalTotal = subTotal + deliveryFee;

        const subTotalEl = document.getElementById('summary-subtotal');
        const deliveryEl = document.getElementById('summary-delivery');
        const totalEl = document.getElementById('summary-total');

        if(subTotalEl) subTotalEl.innerText = `₹${subTotal.toFixed(2)}`;
        if(deliveryEl) deliveryEl.innerText = `₹${deliveryFee.toFixed(2)}`;
        if(totalEl) totalEl.innerText = `₹${finalTotal.toFixed(2)}`;

    } catch (e) {
        console.error("Cart loading error:", e);
    }
}

window.updateQty = async function(skuId, newQty) {
    try {
        await apiCall('/orders/cart/add/', 'POST', {
            sku_id: skuId,
            quantity: newQty
        }, true);
        await loadCart();
        if(typeof updateGlobalCartCount === 'function') {
            updateGlobalCartCount();
        }
    } catch (e) {
        alert("Failed to update cart. Please try again.");
        console.error(e);
    }
};