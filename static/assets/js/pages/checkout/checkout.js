/* static/assets/js/pages/checkout/checkout.js */

let selectedAddressId = null;
let selectedPayment = 'COD';
let cartTotal = 0;

document.addEventListener('DOMContentLoaded', async () => {
    // Auth Check
    if (!localStorage.getItem('access_token')) {
        window.location.href = '/auth.html';
        return;
    }
    loadAddresses();
    loadOrderSummary();
    setupAddressModal();
});

// --- 1. Address Logic ---
async function loadAddresses() {
    const container = document.getElementById('address-list');
    container.innerHTML = '<div class="loader">Loading...</div>';

    try {
        const response = await apiCall('/auth/customer/addresses/'); 
        const addresses = response.results || response; 

        container.innerHTML = '';

        if (!addresses || addresses.length === 0) {
            container.innerHTML = `
                <div class="alert alert-warning">
                    No address found. 
                    <a href="#" onclick="window.LocationPicker.open(); return false;">Add Location</a>
                </div>`;
            return;
        }

        addresses.forEach((addr, index) => {
            const card = document.createElement('div');
            // Auto-select the first/default address
            const isSelected = addr.is_default || index === 0;
            if (isSelected) selectedAddressId = addr.id;

            card.className = `addr-card ${isSelected ? 'selected' : ''}`; 
            card.onclick = () => selectAddr(addr.id, card);

            // Display Logic
            card.innerHTML = `
                <div class="d-flex justify-content-between">
                    <span class="addr-tag">${addr.address_type}</span>
                    ${isSelected ? '<i class="fas fa-check-circle text-success"></i>' : ''}
                </div>
                <strong>${addr.city}</strong>
                <p class="mb-0 text-muted small">${addr.full_address}</p>
                <small>PIN: ${addr.pincode}</small>
            `;
            container.appendChild(card);
        });

    } catch (e) {
        console.error("Address Load Error:", e);
        container.innerHTML = '<p class="text-danger">Failed to load addresses.</p>';
    }
}

function selectAddr(id, el) {
    selectedAddressId = id;
    document.querySelectorAll('.addr-card').forEach(c => c.classList.remove('selected'));
    document.querySelectorAll('.addr-card i.text-success').forEach(i => i.remove());
    
    el.classList.add('selected');
    // Add visual checkmark
    el.querySelector('.d-flex').insertAdjacentHTML('beforeend', '<i class="fas fa-check-circle text-success"></i>');
}

// --- 2. Order Summary ---
async function loadOrderSummary() {
    try {
        const cart = await apiCall('/orders/cart/');
        const subtotal = parseFloat(cart.total_amount);
        cartTotal = subtotal + 20; // Delivery Fee fixed
        
        document.getElementById('checkout-total').innerText = `₹${cartTotal.toFixed(2)}`;
        
        const preview = document.getElementById('checkout-items-preview');
        if(preview && cart.items) {
            preview.innerHTML = cart.items.map(i => 
                `<div class="d-flex justify-content-between small mb-1">
                    <span>${i.quantity} x ${i.sku_name.substring(0, 20)}..</span>
                    <span>₹${i.total_price}</span>
                </div>`
            ).join('');
        }
    } catch(e) {
        console.error("Cart Error", e);
    }
}

// --- 3. Payment Selection ---
window.selectPayment = function(method) {
    selectedPayment = method;
    document.querySelectorAll('.payment-option').forEach(o => o.classList.remove('selected'));
    
    // Find input by value and check it
    const input = document.querySelector(`input[name="payment"][value="${method}"]`);
    if(input) {
        input.checked = true;
        input.closest('.payment-option').classList.add('selected');
    }
};

// --- 4. Place Order ---
document.getElementById('place-order-btn').addEventListener('click', async () => {
    if (!selectedAddressId) {
        alert("Please select a delivery address.");
        return;
    }

    const btn = document.getElementById('place-order-btn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

    try {
        // [STEP 1] Fetch Selected Address Details (To send snapshot)
        const response = await apiCall('/auth/customer/addresses/');
        const addresses = response.results || response;
        const addrObj = addresses.find(a => a.id === selectedAddressId);

        if (!addrObj) throw new Error("Selected address invalid.");

        // [STEP 2] Prepare Payload
        const payload = {
            payment_method: selectedPayment,
            delivery_address_json: {
                full_address: addrObj.full_address,
                city: addrObj.city,
                pincode: addrObj.pincode,
                type: addrObj.address_type
            },
            // Important: Send Lat/Lng if available for rider routing
            delivery_lat: addrObj.location ? addrObj.location.coordinates[1] : null,
            delivery_lng: addrObj.location ? addrObj.location.coordinates[0] : null
        };

        // [STEP 3] Order Create API Call
        const orderData = await apiCall('/orders/create/', 'POST', payload);

        if (selectedPayment === 'COD') {
            window.location.href = `/order_success.html?order_id=${orderData.order.id}`;
        } else {
            // Initiate Razorpay/Stripe here
            alert("Online payment integration required."); 
            window.location.href = `/order_success.html?order_id=${orderData.order.id}`;
        }

    } catch (e) {
        console.error("Order Failed:", e);
        alert("Order Failed: " + (e.message || JSON.stringify(e)));
        btn.disabled = false;
        btn.innerText = "Place Order";
    }
});

// --- 5. Modal Setup (Use Location Picker) ---
window.setupAddressModal = function() {
    // This targets the "Add Address" button on Checkout page
    const addBtn = document.getElementById('add-address-btn');
    
    if (addBtn) {
        addBtn.onclick = (e) => {
            e.preventDefault();
            // Open the Map Modal
            if (window.LocationPicker) {
                window.LocationPicker.open();
            } else {
                console.error("LocationPicker library missing");
            }
        };
    }
};