// assets/js/utils/checkout.js

let selectedAddress = null;
let selectedPaymentMethod = 'COD';
let cartTotal = 0;

document.addEventListener('DOMContentLoaded', async () => {
    if (!isLoggedIn()) window.location.href = 'auth.html';

    await loadAddresses();
    await loadCartSummary();

    // Payment method selection
    document.querySelectorAll('input[name="payment_method"]').forEach(input => {
        input.addEventListener('change', (e) => {
            selectedPaymentMethod = e.target.id === 'payment_cod' ? 'COD' : 'RAZORPAY';
            // Visual update logic (from your css)
            document.querySelectorAll('.payment-option').forEach(opt => opt.classList.remove('selected'));
            e.target.closest('.payment-option').classList.add('selected');
        });
    });

    // Place Order Button
    const placeBtn = document.querySelector('.place-order-button');
    if(placeBtn) {
        placeBtn.addEventListener('click', handlePlaceOrder);
    }
});

async function loadAddresses() {
    const addressContainer = document.querySelector('.checkout-section:first-child'); 
    // Clear old static cards except title
    const title = addressContainer.querySelector('.section-title');
    const addBtn = addressContainer.querySelector('.add-new-address-btn');
    
    // Temporarily remove content to rebuild
    addressContainer.innerHTML = '';
    addressContainer.appendChild(title);

    try {
        const addresses = await apiCall('/auth/customer/addresses/', 'GET', null, true);
        
        if(addresses.length === 0) {
            addressContainer.innerHTML += '<p>No address found. Please add one.</p>';
        } else {
            addresses.forEach((addr, index) => {
                const isSelected = addr.is_default || index === 0;
                if(isSelected) selectedAddress = addr;

                const div = document.createElement('div');
                div.className = `address-card ${isSelected ? 'selected' : ''}`;
                div.onclick = () => selectAddress(addr, div);
                
                div.innerHTML = `
                    <div class="address-radio">
                        <input type="radio" name="delivery_address" ${isSelected ? 'checked' : ''}>
                        <label></label>
                    </div>
                    <div class="address-details">
                        <span class="address-tag">${addr.address_type}</span>
                        <p class="address-name">${addr.city}</p> <p class="address-full">${addr.full_address}, ${addr.city} - ${addr.pincode}</p>
                    </div>
                `;
                addressContainer.appendChild(div);
            });
        }
        addressContainer.appendChild(addBtn); // Add button wapas lagaya

    } catch (e) {
        console.error(e);
    }
}

function selectAddress(addr, divElement) {
    selectedAddress = addr;
    // UI Update
    document.querySelectorAll('.address-card').forEach(c => c.classList.remove('selected'));
    document.querySelectorAll('input[name="delivery_address"]').forEach(i => i.checked = false);
    
    divElement.classList.add('selected');
    divElement.querySelector('input').checked = true;
}

async function loadCartSummary() {
    try {
        const cart = await apiCall('/orders/cart/', 'GET', null, true);
        cartTotal = cart.total_amount;
        
        // Render items summary
        const listContainer = document.querySelector('.summary-items-list');
        if(listContainer) {
            listContainer.innerHTML = cart.items.map(item => `
                <div class="summary-item">
                    <span class="item-name">${item.sku_name} (x${item.quantity})</span>
                    <span class="item-price">₹${item.total_price}</span>
                </div>
            `).join('');
        }

        // Update Totals
        document.getElementById('summary-subtotal').innerText = `₹${cart.total_amount}`;
        const deliveryFee = 20; // Hardcoded for now, or fetch from config
        const total = parseFloat(cart.total_amount) + deliveryFee;
        document.getElementById('summary-total').innerText = `₹${total.toFixed(2)}`;

    } catch (e) {
        console.error("Cart summary failed", e);
    }
}

async function handlePlaceOrder(e) {
    e.preventDefault();
    
    if(!selectedAddress) {
        alert("Please select a delivery address.");
        return;
    }

    // 1. Find Warehouse (Auto-select logic or simple fetch)
    let warehouseId = null;
    try {
        const whs = await apiCall('/wms/warehouses/', 'GET', null, true);
        if(whs && whs.length > 0) warehouseId = whs[0].id; 
    } catch(e) {
        console.error("WH fetch failed", e);
    }

    if(!warehouseId) {
        alert("Sorry, service not available (No warehouse found).");
        return;
    }

    const placeBtn = document.querySelector('.place-order-button');
    placeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    placeBtn.disabled = true;

    // 2. Create Order Payload
    const payload = {
        warehouse_id: warehouseId,
        payment_method: selectedPaymentMethod,
        delivery_address_json: {
            full_address: selectedAddress.full_address,
            city: selectedAddress.city,
            pincode: selectedAddress.pincode,
            type: selectedAddress.address_type
        }
        // Note: delivery_lat/lng can be added if address model has it
    };

    try {
        const resp = await apiCall('/orders/create/', 'POST', payload, true);
        
        if (selectedPaymentMethod === 'COD') {
            // COD Success
            window.location.href = 'order_success.html';
        } else if (selectedPaymentMethod === 'RAZORPAY') {
            // Handle Razorpay Payment
            handleRazorpay(resp);
        }

    } catch (error) {
        alert("Order Failed: " + error.message);
        placeBtn.innerHTML = 'Place Order';
        placeBtn.disabled = false;
    }
}

function handleRazorpay(orderData) {
    // Razorpay integration options
    var options = {
        "key": "YOUR_RAZORPAY_KEY_ID", // Config se aana chahiye
        "amount": orderData.amount * 100, // Paise
        "currency": "INR",
        "name": "QuickDash",
        "description": "Order Payment",
        "order_id": orderData.razorpay_order_id, 
        "handler": async function (response){
            // Verify Payment on Backend
            try {
                const verifyResp = await apiCall('/orders/payment/verify/', 'POST', {
                    razorpay_order_id: response.razorpay_order_id,
                    razorpay_payment_id: response.razorpay_payment_id,
                    razorpay_signature: response.razorpay_signature
                }, true);
                
                if(verifyResp.status === 'success') {
                    window.location.href = 'order_success.html';
                }
            } catch (e) {
                alert("Payment Verification Failed: " + e.message);
            }
        },
        "prefill": {
            "contact": JSON.parse(localStorage.getItem('user'))?.phone || ""
        },
        "theme": {
            "color": "#00a94f"
        }
    };
    
    // Razorpay script load check
    if(window.Razorpay) {
        var rzp1 = new Razorpay(options);
        rzp1.open();
    } else {
        alert("Razorpay SDK not loaded. Please check internet connection.");
    }
}