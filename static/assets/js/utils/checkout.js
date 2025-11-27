// assets/js/utils/checkout.js

let selectedAddress = null;
let selectedPaymentMethod = 'COD';
let cartTotal = 0;
let globalConfig = {}; // Config store karne ke liye

document.addEventListener('DOMContentLoaded', async () => {
    if (!isLoggedIn()) window.location.href = 'auth.html';

    // 1. Load Global Config (Keys & Fees)
    try {
        globalConfig = await apiCall('/utils/config/', 'GET');
    } catch (e) {
        console.error("Config load failed", e);
    }

    await loadAddresses();
    await loadCartSummary();

    // Payment method selection logic
    document.querySelectorAll('input[name="payment_method"]').forEach(input => {
        input.addEventListener('change', (e) => {
            selectedPaymentMethod = e.target.id === 'payment_cod' ? 'COD' : 'RAZORPAY';
            // Visual update
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
    const title = addressContainer.querySelector('.section-title');
    const addBtn = addressContainer.querySelector('.add-new-address-btn');
    
    addressContainer.innerHTML = '';
    addressContainer.appendChild(title);

    try {
        // Fetch Addresses from API
        const addresses = await apiCall('/auth/customer/addresses/', 'GET', null, true);
        
        if(addresses.length === 0) {
            const msg = document.createElement('p');
            msg.innerText = 'No address found. Please add one.';
            addressContainer.appendChild(msg);
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
                        <p class="address-name">${addr.city}</p> 
                        <p class="address-full">${addr.full_address}, ${addr.city} - ${addr.pincode}</p>
                    </div>
                `;
                addressContainer.appendChild(div);
            });
        }
        if(addBtn) addressContainer.appendChild(addBtn);

    } catch (e) {
        console.error(e);
    }
}

function selectAddress(addr, divElement) {
    selectedAddress = addr;
    document.querySelectorAll('.address-card').forEach(c => c.classList.remove('selected'));
    document.querySelectorAll('input[name="delivery_address"]').forEach(i => i.checked = false);
    
    divElement.classList.add('selected');
    const radio = divElement.querySelector('input');
    if(radio) radio.checked = true;
}

async function loadCartSummary() {
    try {
        const cart = await apiCall('/orders/cart/', 'GET', null, true);
        cartTotal = cart.total_amount;
        
        const listContainer = document.querySelector('.summary-items-list');
        if(listContainer) {
            listContainer.innerHTML = cart.items.map(item => `
                <div class="summary-item">
                    <span class="item-name">${item.sku_name} (x${item.quantity})</span>
                    <span class="item-price">₹${item.total_price}</span>
                </div>
            `).join('');
        }

        // Calculations using API values
        const deliveryFee = parseFloat(globalConfig.base_delivery_fee || 20.00); 
        const subTotal = parseFloat(cart.total_amount);
        const total = subTotal + deliveryFee;

        document.getElementById('summary-subtotal').innerText = `₹${subTotal.toFixed(2)}`;
        document.getElementById('summary-delivery').innerText = `₹${deliveryFee.toFixed(2)}`;
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

    // [Logic] Warehouse selection ab backend handle karega based on lat/lng (agar available hain)
    // Lekin agar logic client side rakhna hai toh pehle warehouse fetch karo.
    // Behtar ye hai ki hum lat/lng bhejein aur backend decide kare.
    
    const placeBtn = document.querySelector('.place-order-button');
    const originalText = placeBtn.innerHTML;
    placeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    placeBtn.disabled = true;

    // Payload construction - Ab coordinates bhi bhej rahe hain
    const payload = {
        // warehouse_id: auto-selected by backend if lat/lng present
        payment_method: selectedPaymentMethod,
        delivery_address_json: {
            full_address: selectedAddress.full_address,
            city: selectedAddress.city,
            pincode: selectedAddress.pincode,
            type: selectedAddress.address_type
        },
        // [NEW] Backend needs coordinates for Rider & Warehouse matching
        delivery_lat: selectedAddress.location ? selectedAddress.location.coordinates[1] : null, 
        delivery_lng: selectedAddress.location ? selectedAddress.location.coordinates[0] : null
    };

    try {
        // Step 1: Create Order
        const resp = await apiCall('/orders/create/', 'POST', payload, true);
        
        if (selectedPaymentMethod === 'COD') {
            window.location.href = 'order_success.html';
        } else if (selectedPaymentMethod === 'RAZORPAY') {
            // Step 2: Handle Online Payment
            handleRazorpay(resp);
        }

    } catch (error) {
        alert("Order Failed: " + error.message);
        placeBtn.innerHTML = originalText;
        placeBtn.disabled = false;
    }
}

function handleRazorpay(orderData) {
    // Check if SDK loaded
    if(!window.Razorpay) {
        alert("Razorpay SDK failed to load. Please check your internet.");
        window.location.reload();
        return;
    }

    // [FIXED] Key is now dynamic from API
    var options = {
        "key": globalConfig.razorpay_key_id, 
        "amount": orderData.amount * 100, // Amount in paise
        "currency": "INR",
        "name": "QuickDash",
        "description": "Order Payment",
        "order_id": orderData.razorpay_order_id, 
        "handler": async function (response){
            try {
                // Step 3: Verify Payment
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
                // Redirect to orders page so user can retry payment or see status
                window.location.href = 'profile.html';
            }
        },
        "prefill": {
            "contact": JSON.parse(localStorage.getItem('user'))?.phone || ""
        },
        "theme": {
            "color": "#00a94f"
        }
    };
    
    var rzp1 = new Razorpay(options);
    rzp1.on('payment.failed', function (response){
        alert("Payment Failed: " + response.error.description);
    });
    rzp1.open();
}