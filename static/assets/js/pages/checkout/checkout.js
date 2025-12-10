// static/assets/js/pages/checkout/checkout.js
let selectedAddressId = null;
let selectedPayment = 'COD';
let cartTotal = 0;

document.addEventListener('DOMContentLoaded', async () => {
    if (!APP_CONFIG.IS_LOGGED_IN) {
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
            container.innerHTML = '<p class="text-muted">No addresses found. Please add one.</p>';
            return;
        }

        addresses.forEach((addr, index) => {
            const card = document.createElement('div');
            const isSelected = index === 0;
            if (isSelected) selectedAddressId = addr.id;

            card.className = `addr-card ${isSelected ? 'selected' : ''}`; 
            card.onclick = () => selectAddr(addr.id, card);

            card.innerHTML = `
                <span class="addr-tag">${addr.address_type}</span>
                <strong>${addr.city}</strong>
                <p class="mb-0 text-muted" style="font-size:0.9rem">${addr.full_address} - ${addr.pincode}</p>
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
    el.classList.add('selected');
}

// --- 2. Order Summary ---
async function loadOrderSummary() {
    try {
        const cart = await apiCall('/orders/cart/');
        const subtotal = parseFloat(cart.total_amount);
        cartTotal = subtotal + 20; // Delivery Fee
        
        document.getElementById('checkout-total').innerText = `₹${cartTotal.toFixed(2)}`;
        
        const preview = document.getElementById('checkout-items-preview');
        preview.innerHTML = cart.items.map(i => 
            `<div style="display:flex; justify-content:space-between; font-size:0.85rem; margin-bottom:5px;">
                <span>${i.quantity} x ${i.sku_name.substring(0, 15)}...</span>
                <span>₹${i.total_price}</span>
            </div>`
        ).join('');
    } catch(e) {
        console.error("Cart Error", e);
    }
}

// --- Payment Selection ---
window.selectPayment = function(method) {
    selectedPayment = method;
    document.querySelectorAll('.payment-option').forEach(o => o.classList.remove('selected'));
    const input = document.querySelector(`input[value="${method}"]`);
    if(input) {
        input.checked = true;
        input.closest('.payment-option').classList.add('selected');
    }
};

// --- 3. Place Order ---
document.getElementById('place-order-btn').addEventListener('click', async () => {
    if (!selectedAddressId) {
        alert("Please select a delivery address.");
        return;
    }

    const btn = document.getElementById('place-order-btn');
    btn.disabled = true;
    btn.innerText = "Processing...";

    try {
        // [STEP 1] Fetch Selected Address Details
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
                pincode: addrObj.pincode
            },
            // FIX: Use address coordinates if available, otherwise allow backend to handle it (do not hardcode)
            delivery_lat: addrObj.latitude || addrObj.lat || null, 
            delivery_lng: addrObj.longitude || addrObj.lng || null
        };

        // [STEP 3] Order Create API Call
        const orderData = await apiCall('/orders/create/', 'POST', payload);

        if (selectedPayment === 'COD') {
            window.location.href = `/order_success.html?order_id=${orderData.order.id}`;
        } else {
            await handleRazorpay(orderData);
        }

    } catch (e) {
        console.error("Order Failed:", e);
        alert("Order Failed: " + (e.message || JSON.stringify(e)));
        btn.disabled = false;
        btn.innerText = "Place Order";
    }
});

// --- 4. Razorpay Integration ---
async function handleRazorpay(orderData) {
    if (!orderData.razorpay_order_id) {
        alert("Payment initialization failed. Please try COD.");
        document.getElementById('place-order-btn').disabled = false;
        return;
    }

    let keyId = null;
    try {
        const config = await apiCall('/utils/config/', 'GET', null, false);
        if (config.razorpay_key_id) keyId = config.razorpay_key_id;
    } catch (e) {
        console.warn("Config fetch failed");
    }

    // FIX: Do not use a fallback key that breaks in prod. Fail fast.
    if (!keyId || keyId === "rzp_test_placeholder") {
        alert("Payment configuration missing. Please contact support or use COD.");
        document.getElementById('place-order-btn').disabled = false;
        return;
    }

    const options = {
        "key": keyId, 
        "amount": orderData.amount,
        "currency": "INR",
        "name": "QuickDash",
        "description": "Order Payment",
        "image": "/static/assets/img/robot_icon.png", 
        "order_id": orderData.razorpay_order_id, 
        "handler": async function (response) {
            await verifyPayment(response, orderData.order_id);
        },
        "prefill": {
            "name": APP_CONFIG.USER?.full_name || "",
            "contact": APP_CONFIG.USER?.phone || ""
        },
        "theme": {
            "color": "#32CD32" 
        },
        "modal": {
            "ondismiss": function(){
                document.getElementById('place-order-btn').disabled = false;
                document.getElementById('place-order-btn').innerText = "Place Order";
                alert('Payment cancelled.');
            }
        }
    };

    const rzp1 = new Razorpay(options);
    
    rzp1.on('payment.failed', function (response){
        alert("Payment Failed: " + response.error.description);
        document.getElementById('place-order-btn').disabled = false;
    });

    rzp1.open();
}

async function verifyPayment(paymentResponse, localOrderId) {
    const btn = document.getElementById('place-order-btn');
    btn.innerText = "Verifying...";

    try {
        const verifyPayload = {
            payment_intent_id: localOrderId,
            razorpay_order_id: paymentResponse.razorpay_order_id,
            razorpay_payment_id: paymentResponse.razorpay_payment_id,
            razorpay_signature: paymentResponse.razorpay_signature
        };

        await apiCall('/orders/payment/verify/', 'POST', verifyPayload);
        window.location.href = `/order_success.html?order_id=${localOrderId}`;

    } catch (e) {
        alert("Payment verification failed. Contact support.");
        window.location.href = `/orders.html`;
    }
}

// --- Modal Setup ---
window.setupAddressModal = function() {
    const modal = document.getElementById('address-modal');
    if (!modal) return;

    const addBtn = document.getElementById('add-address-btn');
    if (addBtn) addBtn.onclick = () => modal.style.display = 'flex';
    
    window.closeModal = () => modal.style.display = 'none';

    const form = document.getElementById('new-address-form');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            // FIX: Removed hardcoded lat/lng. Send blank if unknown.
            const payload = {
                full_address: document.getElementById('addr-line').value,
                city: document.getElementById('addr-city').value,
                pincode: document.getElementById('addr-pincode').value,
                address_type: document.getElementById('addr-type').value,
                // Optional: If you have a map picker, add lat/lng here.
            };

            try {
                await apiCall('/auth/customer/addresses/', 'POST', payload);
                closeModal();
                loadAddresses(); 
            } catch(err) {
                alert(err.message);
            }
        });
    }
};