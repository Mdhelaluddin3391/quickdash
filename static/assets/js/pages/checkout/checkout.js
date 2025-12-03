let selectedAddressId = null;
let selectedPayment = 'COD';
let cartTotal = 0;
let currentLat = null;
let currentLng = null;

document.addEventListener('DOMContentLoaded', async () => {
    if (!APP_CONFIG.IS_LOGGED_IN) {
        window.location.href = '/auth.html';
        return;
    }
    loadAddresses();
    loadOrderSummary();
    setupAddressModal();
});

// --- Address Logic ---
async function loadAddresses() {
    const container = document.getElementById('address-list');
    try {
        const addresses = await apiCall('/auth/customer/addresses/'); // List
        container.innerHTML = '';

        if (addresses.length === 0) {
            container.innerHTML = '<p class="text-muted">No addresses found.</p>';
            return;
        }

        addresses.forEach((addr, index) => {
            const card = document.createElement('div');
            card.className = `addr-card ${index === 0 ? 'selected' : ''}`; // Auto-select first
            card.onclick = () => selectAddr(addr.id, card);
            if (index === 0) selectedAddressId = addr.id;

            card.innerHTML = `
                <span class="addr-tag">${addr.address_type}</span>
                <strong>${addr.city}</strong>
                <p class="mb-0 text-muted" style="font-size:0.9rem">${addr.full_address} - ${addr.pincode}</p>
            `;
            container.appendChild(card);
        });

    } catch (e) {
        console.error("Addr Error", e);
    }
}

function selectAddr(id, el) {
    selectedAddressId = id;
    document.querySelectorAll('.addr-card').forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');
}

// --- Order Summary ---
async function loadOrderSummary() {
    const cart = await apiCall('/orders/cart/');
    cartTotal = parseFloat(cart.total_amount) + 20; // + Fee
    document.getElementById('checkout-total').innerText = `₹${cartTotal.toFixed(2)}`;
    
    // Mini preview
    const preview = document.getElementById('checkout-items-preview');
    preview.innerHTML = cart.items.map(i => 
        `<div style="display:flex; justify-content:space-between; font-size:0.85rem; margin-bottom:5px;">
            <span>${i.quantity} x ${i.sku_name.substring(0, 15)}...</span>
            <span>₹${i.total_price}</span>
        </div>`
    ).join('');
}

// --- Payment Select ---
window.selectPayment = function(method) {
    selectedPayment = method;
    document.querySelectorAll('.payment-option').forEach(o => o.classList.remove('selected'));
    // Visual logic handled by input:checked CSS, but we ensure class updates for borders
    const input = document.querySelector(`input[value="${method}"]`);
    if(input) {
        input.checked = true;
        input.closest('.payment-option').classList.add('selected');
    }
};


window.setupAddressModal = function() {
    const modal = document.getElementById('address-modal');
    
    // Add "Use My Location" button dynamically if not exists
    const form = document.getElementById('new-address-form');
    if (!document.getElementById('btn-gps')) {
        const gpsBtn = document.createElement('button');
        gpsBtn.type = 'button';
        gpsBtn.id = 'btn-gps';
        gpsBtn.className = 'btn-outline mb-3';
        gpsBtn.style.width = '100%';
        gpsBtn.innerHTML = '<i class="fas fa-crosshairs"></i> Use Current Location';
        gpsBtn.onclick = getUserLocation;
        form.insertBefore(gpsBtn, form.firstChild);
    }

    document.getElementById('add-address-btn').onclick = () => modal.style.display = 'flex';
    window.closeModal = () => modal.style.display = 'none';

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Use GPS coords if fetched, else default (Bangalore)
        const lat = currentLat || 12.9716;
        const lng = currentLng || 77.5946;

        const payload = {
            full_address: document.getElementById('addr-line').value,
            city: document.getElementById('addr-city').value,
            pincode: document.getElementById('addr-pincode').value,
            address_type: document.getElementById('addr-type').value,
            lat: lat, 
            lng: lng
        };

        try {
            const btn = form.querySelector('button[type="submit"]');
            btn.innerText = "Saving...";
            await apiCall('/auth/customer/addresses/', 'POST', payload);
            closeModal();
            loadAddresses(); // Refresh list
            btn.innerText = "Save Address";
        } catch(err) {
            alert(err.message);
        }
    });
};

function getUserLocation() {
    const btn = document.getElementById('btn-gps');
    if (!navigator.geolocation) {
        alert("Geolocation is not supported by your browser.");
        return;
    }
    btn.innerText = "Locating...";
    navigator.geolocation.getCurrentPosition(
        (position) => {
            currentLat = position.coords.latitude;
            currentLng = position.coords.longitude;
            btn.innerHTML = '<i class="fas fa-check"></i> Location Fetched!';
            btn.style.borderColor = '#32CD32';
            btn.style.color = '#32CD32';
        },
        (error) => {
            alert("Unable to retrieve your location. Please enter manually.");
            btn.innerText = "Use Current Location";
        }
    );
}

// --- Place Order ---
document.getElementById('place-order-btn').addEventListener('click', async () => {
    if (!selectedAddressId) {
        alert("Please select a delivery address.");
        return;
    }

    const btn = document.getElementById('place-order-btn');
    btn.disabled = true;
    btn.innerText = "Processing...";

    try {
        // 1. Get Address Details (Backend requires JSON blob currently, based on your serializer)
        // Optimization: In a real app, send ID. But your CreateOrderSerializer expects 'delivery_address_json'.
        // So let's fetch the full object again or store it in DOM. 
        // For simplicity, I will re-fetch the specific address or iterate my local list.
        const addresses = await apiCall('/auth/customer/addresses/');
        const addrObj = addresses.find(a => a.id === selectedAddressId);

        const payload = {
            warehouse_id: "1", // Ideally dynamic based on lat/lng or user selection
            payment_method: selectedPayment,
            delivery_address_json: {
                full_address: addrObj.full_address,
                city: addrObj.city,
                pincode: addrObj.pincode
            },
            // Include lat/lng if available in addrObj
            delivery_lat: addrObj.latitude, 
            delivery_lng: addrObj.longitude
        };

        const response = await apiCall('/orders/create/', 'POST', payload);

        if (selectedPayment === 'COD') {
            window.location.href = `/order_success.html?order_id=${response.order.id}`;
        } else {
            // Razorpay Handling
            handleRazorpay(response);
        }

    } catch (e) {
        alert(e.message);
        btn.disabled = false;
        btn.innerText = "Place Order";
    }
});

// --- Modal Logic ---
window.setupAddressModal = function() {
    const modal = document.getElementById('address-modal');
    document.getElementById('add-address-btn').onclick = () => modal.style.display = 'flex';
    window.closeModal = () => modal.style.display = 'none';

    document.getElementById('new-address-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            full_address: document.getElementById('addr-line').value,
            city: document.getElementById('addr-city').value,
            pincode: document.getElementById('addr-pincode').value,
            address_type: document.getElementById('addr-type').value,
            // Hardcoding lat/lng for demo as we removed the map selector for simplicity
            lat: 12.9716, lng: 77.5946 
        };

        try {
            await apiCall('/auth/customer/addresses/', 'POST', payload);
            closeModal();
            loadAddresses(); // Refresh list
        } catch(err) {
            alert(err.message);
        }
    });
};

// ... (Keep existing loadAddresses, selectAddr, loadOrderSummary logic) ...

async function handleRazorpay(orderData) {
    if (!orderData.razorpay_order_id) {
        alert("Payment initialization failed. Please try COD.");
        return;
    }

    // Fetch Key ID from Backend Config (Secure way)
    let keyId = "rzp_test_YOUR_KEY_HERE"; // Fallback
    try {
        const config = await apiCall('/utils/config/', 'GET', null, false);
        if (config.razorpay_key_id) keyId = config.razorpay_key_id;
    } catch (e) {
        console.warn("Could not fetch config, using fallback key or failing safely");
    }

    const options = {
        "key": keyId, 
        "amount": orderData.amount, // Amount in paise
        "currency": "INR",
        "name": "QuickDash",
        "description": "Order Payment",
        "image": "/static/assets/img/logo.png", // Add your logo here
        "order_id": orderData.razorpay_order_id, 
        "handler": async function (response) {
            // Success Callback
            await verifyPayment(response, orderData.order_id);
        },
        "prefill": {
            "name": APP_CONFIG.USER?.full_name || "",
            "email": APP_CONFIG.USER?.email || "",
            "contact": APP_CONFIG.USER?.phone || ""
        },
        "theme": {
            "color": "#32CD32" // QuickDash Green
        }
    };

    const rzp1 = new Razorpay(options);
    
    rzp1.on('payment.failed', function (response){
        alert("Payment Failed: " + response.error.description);
    });

    rzp1.open();
}

async function verifyPayment(paymentResponse, localOrderId) {
    // Show processing state
    const btn = document.getElementById('place-order-btn');
    btn.innerText = "Verifying...";

    try {
        const payload = {
            payment_intent_id: paymentResponse.razorpay_order_id, // Mapping intention
            gateway_order_id: paymentResponse.razorpay_order_id,
            gateway_payment_id: paymentResponse.razorpay_payment_id,
            gateway_signature: paymentResponse.razorpay_signature
        };

        // Note: Backend endpoint might vary, adjusting to your apps/payments/views.py
        // Your PaymentVerificationView expects: razorpay_order_id, razorpay_payment_id, razorpay_signature
        const verifyPayload = {
            razorpay_order_id: paymentResponse.razorpay_order_id,
            razorpay_payment_id: paymentResponse.razorpay_payment_id,
            razorpay_signature: paymentResponse.razorpay_signature
        };

        await apiCall('/orders/payment/verify/', 'POST', verifyPayload);
        
        // Redirect on Success
        window.location.href = `/order_success.html?order_id=${localOrderId}`;

    } catch (e) {
        console.error(e);
        alert("Payment verification failed, but amount may be deducted. Contact support.");
        // Redirect anyway to let them check status on Order Detail
        window.location.href = `/orders.html`;
    }
}