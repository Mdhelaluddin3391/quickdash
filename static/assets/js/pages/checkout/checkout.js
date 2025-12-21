/* static/assets/js/pages/checkout/checkout.js */

let selectedAddressId = null;
let selectedPayment = 'COD';
let cartTotal = 0;
let addressStore = []; // Cache addresses to avoid re-fetching

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Auth Check
    if (window.APP_CONFIG && !window.APP_CONFIG.IS_LOGGED_IN) {
        window.location.href = window.APP_CONFIG.URLS.LOGIN;
        return;
    }

    // 2. Load Data
    await Promise.all([
        loadAddresses(),
        loadOrderSummary()
    ]);
    
    // 3. Setup Modals
    setupAddressModal();
});

// --- 1. Address Logic ---
async function loadAddresses() {
    const container = document.getElementById('address-list');
    if(!container) return;
    
    container.innerHTML = '<div class="loader text-center"><div class="spinner-border text-success"></div></div>';

    try {
        const response = await apiCall('/auth/customer/addresses/'); 
        addressStore = response.results || response; // Cache it

        container.innerHTML = '';

        if (!addressStore || addressStore.length === 0) {
            container.innerHTML = `
                <div class="alert alert-warning">
                    No address found. 
                    <a href="#" onclick="if(window.LocationPicker) window.LocationPicker.open(); return false;">Add Location</a>
                </div>`;
            return;
        }

        addressStore.forEach((addr, index) => {
            const card = document.createElement('div');
            // Auto-select the first/default address
            const isSelected = addr.is_default || index === 0;
            if (isSelected) selectedAddressId = addr.id;

            card.className = `addr-card ${isSelected ? 'selected' : ''}`; 
            card.onclick = () => selectAddr(addr.id, card);

            // Display Logic
            const icon = addr.address_type === 'HOME' ? 'fa-home' : 'fa-briefcase';
            
            card.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span class="addr-tag"><i class="fas ${icon}"></i> ${addr.address_type}</span>
                    ${isSelected ? '<i class="fas fa-check-circle text-success check-icon"></i>' : ''}
                </div>
                <div class="mt-2">
                    <strong>${addr.city || 'Unknown City'}</strong>
                    <p class="mb-0 text-muted small" style="line-height:1.4;">
                        ${addr.full_address || addr.address_text || 'No details provided'}
                    </p>
                    <small class="text-secondary">PIN: ${addr.pincode}</small>
                </div>
            `;
            container.appendChild(card);
        });

    } catch (e) {
        console.error("Address Load Error:", e);
        container.innerHTML = '<p class="text-danger text-center">Failed to load addresses.</p>';
    }
}

function selectAddr(id, el) {
    selectedAddressId = id;
    
    // Visual Update
    document.querySelectorAll('.addr-card').forEach(c => {
        c.classList.remove('selected');
        const icon = c.querySelector('.check-icon');
        if(icon) icon.remove();
    });
    
    el.classList.add('selected');
    const header = el.querySelector('.d-flex');
    if(header) header.insertAdjacentHTML('beforeend', '<i class="fas fa-check-circle text-success check-icon"></i>');
}

// --- 2. Order Summary ---
async function loadOrderSummary() {
    try {
        const cart = await apiCall('/orders/cart/');
        
        // Safety check: Is cart empty?
        if(!cart.items || cart.items.length === 0) {
            document.getElementById('checkout-items-preview').innerHTML = 
                '<div class="alert alert-danger">Your cart is empty! <a href="/index.html">Shop Now</a></div>';
            document.getElementById('place-order-btn').disabled = true;
            return;
        }

        const subtotal = parseFloat(cart.total_amount || 0);
        const fee = 20; // Delivery Fee
        cartTotal = subtotal + fee;
        
        const totalEl = document.getElementById('checkout-total');
        if(totalEl) totalEl.innerText = `₹${cartTotal.toFixed(2)}`;
        
        const preview = document.getElementById('checkout-items-preview');
        if(preview) {
            preview.innerHTML = cart.items.map(i => `
                <div class="d-flex justify-content-between small mb-2 border-bottom pb-2">
                    <div style="max-width: 70%;">
                        <span class="fw-bold">${i.quantity} x</span> ${i.sku_name}
                    </div>
                    <span class="fw-bold">₹${i.total_price}</span>
                </div>`
            ).join('');
        }
    } catch(e) {
        console.error("Cart Summary Error", e);
    }
}

// --- 3. Payment Selection ---
window.selectPayment = function(method) {
    selectedPayment = method;
    
    // Visual Update
    document.querySelectorAll('.payment-option').forEach(o => o.classList.remove('selected'));
    
    const input = document.querySelector(`input[name="payment"][value="${method}"]`);
    if(input) {
        input.checked = true;
        const card = input.closest('.payment-option');
        if(card) card.classList.add('selected');
    }
};

// --- 4. Place Order (ROBUST) ---
const placeOrderBtn = document.getElementById('place-order-btn');
if(placeOrderBtn) {
    placeOrderBtn.addEventListener('click', async () => {
        if (!selectedAddressId) {
            if(window.showToast) showToast("Please select a delivery address.", "warning");
            else alert("Please select a delivery address.");
            return;
        }

        const btn = document.getElementById('place-order-btn');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

        try {
            // [STEP 1] Get Address from Cache (No need to re-fetch)
            // Ensure ID type match (int vs string)
            const addrObj = addressStore.find(a => String(a.id) === String(selectedAddressId));

            if (!addrObj) throw new Error("Selected address is invalid or not found.");

            // [STEP 2] Prepare Payload
            // Safety: Ensure location exists before accessing coordinates
            const lat = (addrObj.location && addrObj.location.coordinates) ? addrObj.location.coordinates[1] : null;
            const lng = (addrObj.location && addrObj.location.coordinates) ? addrObj.location.coordinates[0] : null;

            const payload = {
                payment_method: selectedPayment,
                delivery_address_json: {
                    full_address: addrObj.full_address || addrObj.address_text || "",
                    city: addrObj.city || "",
                    pincode: addrObj.pincode || "",
                    type: addrObj.address_type || "HOME"
                },
                delivery_lat: lat,
                delivery_lng: lng
            };

            console.log("Submitting Order Payload:", payload);

            // [STEP 3] Create Order API
            const orderData = await apiCall('/orders/create/', 'POST', payload);

            // [STEP 4] Handle Success / Redirect
            if (selectedPayment === 'COD') {
                window.location.href = `/templates/frontend/checkout/success.html?order_id=${orderData.order.id}`;
            } else if (selectedPayment === 'RAZORPAY') {
                if (!orderData.payment_data || !orderData.payment_data.razorpay_order_id) {
                    throw new Error("Invalid payment initialization from server.");
                }
                await initiateRazorpayPayment(orderData.order || {id: orderData.order_id}, orderData.payment_data);
            }

        } catch (e) {
            console.error("Order Creation Failed:", e);
            
            // BETTER ERROR HANDLING
            let errorMsg = "Order Failed. ";
            if (e.message) errorMsg += e.message;
            // Attempt to show backend field errors if present
            if(e.detail) errorMsg += " (" + e.detail + ")";
            
            if(window.showToast) showToast(errorMsg, "error");
            else alert(errorMsg);
            
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    });
}

// --- Helper: Razorpay ---
async function initiateRazorpayPayment(order, paymentData) {
    if (!document.querySelector('script[src="https://checkout.razorpay.com/v1/checkout.js"]')) {
        await new Promise((resolve) => {
            const script = document.createElement('script');
            script.src = "https://checkout.razorpay.com/v1/checkout.js";
            script.onload = resolve;
            document.body.appendChild(script);
        });
    }

    const options = {
        "key": paymentData.key_id, 
        "amount": paymentData.amount, 
        "currency": paymentData.currency,
        "name": "QuickDash",
        "description": `Order #${order.id}`,
        "order_id": paymentData.razorpay_order_id,
        "prefill": {
            "name": window.APP_CONFIG?.USER?.first_name || "Customer", 
            "contact": window.APP_CONFIG?.USER?.phone || ""
        },
        "theme": { "color": "#32CD32" },
        "handler": async function (response) {
            await verifyPaymentOnBackend(response, order.id);
        },
        "modal": {
            "ondismiss": function() {
                const btn = document.getElementById('place-order-btn');
                btn.disabled = false;
                btn.innerText = "Retry Payment";
                if(window.showToast) showToast('Payment cancelled.', 'info');
            }
        }
    };

    const rzp1 = new Razorpay(options);
    rzp1.on('payment.failed', function (response){
        console.error(response.error);
        if(window.showToast) showToast("Payment Failed: " + response.error.description, "error");
        else alert("Payment Failed");
        
        const btn = document.getElementById('place-order-btn');
        btn.disabled = false;
        btn.innerText = "Retry Payment";
    });
    rzp1.open();
}

async function verifyPaymentOnBackend(rzpResponse, orderId) {
    const btn = document.getElementById('place-order-btn');
    btn.innerHTML = '<i class="fas fa-shield-alt"></i> Verifying...';

    try {
        const payload = {
            razorpay_order_id: rzpResponse.razorpay_order_id,
            razorpay_payment_id: rzpResponse.razorpay_payment_id,
            razorpay_signature: rzpResponse.razorpay_signature
        };

        const verifyResult = await apiCall('/orders/verify-payment/', 'POST', payload);

        if (verifyResult.status === 'success') {
            window.location.href = `/templates/frontend/checkout/success.html?order_id=${orderId}`;
        } else {
            throw new Error("Payment verification failed.");
        }
    } catch (e) {
        console.error("Verification Error:", e);
        alert("Payment verification failed. Please contact support.");
        btn.innerText = "Verification Failed";
    }
}

// --- 5. Modal Bridge ---
window.setupAddressModal = function() {
    const addBtn = document.getElementById('add-address-btn');
    if (addBtn) {
        addBtn.onclick = (e) => {
            e.preventDefault();
            if (window.LocationPicker) {
                window.LocationPicker.open();
            } else {
                console.error("LocationPicker module missing");
            }
        };
    }
};