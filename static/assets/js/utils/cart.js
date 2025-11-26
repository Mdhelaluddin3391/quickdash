// assets/js/utils/cart.js

document.addEventListener('DOMContentLoaded', loadCart);

// Global settings fetch karne ke liye helper function
async function fetchGlobalSettings() {
    try {
        // API call to new config endpoint
        const config = await apiCall('/utils/config/', 'GET');
        return parseFloat(config.base_delivery_fee);
    } catch (error) {
        console.warn("Delivery fee fetch failed, using fallback value.", error);
        return 20.00; // Fallback value agar API fail ho jaye
    }
}

async function loadCart() {
    const listContainer = document.querySelector('.cart-items-list');
    const emptyMsg = document.querySelector('.empty-cart-message');
    const summaryContainer = document.querySelector('.order-summary-container');

    // Auth check
    if (!isLoggedIn()) {
        window.location.href = 'auth.html';
        return;
    }

    try {
        // Promise.all ka use karke Cart aur Settings dono ek saath mangwayenge (Fast loading)
        const [cart, deliveryFee] = await Promise.all([
            apiCall('/orders/cart/', 'GET', null, true),
            fetchGlobalSettings()
        ]);

        // 1. Check agar cart khaali hai
        if (!cart.items || cart.items.length === 0) {
            if(emptyMsg) emptyMsg.style.display = 'block';
            if(summaryContainer) summaryContainer.style.display = 'none';
            
            // Purane items hatao (cleanup)
            const oldItems = document.querySelectorAll('.cart-item');
            oldItems.forEach(el => el.remove());
            return;
        }

        // 2. Agar items hain to UI update karein
        if(emptyMsg) emptyMsg.style.display = 'none';
        if(summaryContainer) summaryContainer.style.display = 'block';

        // Pehle existing items clear karte hain
        const existingItems = document.querySelectorAll('.cart-item');
        existingItems.forEach(e => e.remove());

        // Header ke baad naye items insert karne ke liye reference
        const header = document.querySelector('.cart-header');

        // 3. Items Render karna
        cart.items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'cart-item';
            
            // Image fallback logic
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
            
            // List mein add karein
            if(header && header.parentNode) {
                header.parentNode.insertBefore(div, header.nextSibling);
            }
        });

        // 4. Order Summary Update (Dynamic Calculations)
        const subTotal = parseFloat(cart.total_amount);
        const finalTotal = subTotal + deliveryFee;

        const subTotalEl = document.getElementById('summary-subtotal');
        const deliveryEl = document.getElementById('summary-delivery');
        const totalEl = document.getElementById('summary-total');

        if(subTotalEl) subTotalEl.innerText = `₹${subTotal.toFixed(2)}`;
        
        // Yahan ab API se aayi value dikhegi (Hardcoded nahi)
        if(deliveryEl) deliveryEl.innerText = `₹${deliveryFee.toFixed(2)}`;
        
        if(totalEl) totalEl.innerText = `₹${finalTotal.toFixed(2)}`;

    } catch (e) {
        console.error("Cart loading error:", e);
        // Optional: User ko error toast dikha sakte hain
    }
}

// Quantity Update / Remove Function
window.updateQty = async function(skuId, newQty) {
    try {
        // Button ko disable ya loader dikhana accha UX hota hai (optional enhancement)
        
        // API call: Agar quantity 0 hai to backend item delete kar dega
        await apiCall('/orders/cart/add/', 'POST', {
            sku_id: skuId,
            quantity: newQty
        }, true);
        
        // UI Refresh: Cart reload karein taaki nayi prices aur items dikhen
        await loadCart();
        
        // Global cart count (header mein) bhi update karein
        if(typeof updateGlobalCartCount === 'function') {
            updateGlobalCartCount();
        }

    } catch (e) {
        alert("Failed to update cart. Please try again.");
        console.error(e);
    }
};