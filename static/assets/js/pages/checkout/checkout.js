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

function handleRazorpay(orderData) {
    // This function assumes globalConfig is loaded or Razorpay key is present
    alert("Online payment integration requires Razorpay Key ID configuration. Proceeding as COD for demo.");
    window.location.href = `/order_success.html?order_id=${orderData.order_id || 'TEMP'}`;
}