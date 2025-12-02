// static/assets/js/utils/profile.js

document.addEventListener('DOMContentLoaded', async () => {
    if (!isLoggedIn()) window.location.href = 'auth.html';

    // 1. Load User Info
    const userStr = localStorage.getItem('user');
    if(userStr) {
        try {
            const user = JSON.parse(userStr);
            document.querySelector('.user-name').innerText = user.full_name || "Guest User";
            document.querySelector('.user-phone').innerText = user.phone || "";
            const avatar = document.querySelector('.user-avatar');
            if(avatar) avatar.innerText = (user.full_name || "U").charAt(0).toUpperCase();
        } catch(e) { console.error("User data parse error", e); }
    }

    // 2. Load Data (Order change: Pehle addresses load karo, taaki error aaye to bhi address dikhe)
    await loadAddresses(); 
    
    // Ab Orders load karo (function neeche add kiya hai)
    try {
        await loadOrders(); 
    } catch (e) {
        console.error("Order loading failed but continuing...", e);
    }

    // 3. Address Modal Toggles
    setupAddressModal();
});

// --- NEW FUNCTION: LOAD ORDERS ---
async function loadOrders() {
    const list = document.getElementById('orders');
    if(!list) return;

    list.innerHTML = '<h2 class="content-title">Order History</h2><div style="text-align:center; padding:20px;">Loading orders...</div>';

    try {
        const response = await apiCall('/orders/', 'GET', null, true);
        const orders = response.results || response; // Handle pagination

        if (!orders || orders.length === 0) {
            list.innerHTML = `
                <h2 class="content-title">Order History</h2>
                <div style="text-align:center; padding:40px; color:#777;">
                    <i class="fas fa-box-open" style="font-size:3rem; margin-bottom:10px;"></i>
                    <p>No orders yet.</p>
                    <a href="index.html" class="btn btn-primary" style="margin-top:10px;">Start Shopping</a>
                </div>`;
            return;
        }

        let html = `<h2 class="content-title">Order History</h2>`;
        
        html += orders.map(order => `
            <div class="order-card">
                <div class="order-header">
                    <span class="order-id">Order #${order.id.slice(0, 8).toUpperCase()}</span>
                    <span class="order-status ${order.status}">${order.status}</span>
                </div>
                <div class="order-details">
                    <p><strong>Date:</strong> ${new Date(order.created_at).toLocaleDateString()}</p>
                    <p><strong>Total:</strong> ₹${parseFloat(order.final_amount).toFixed(2)}</p>
                    <p><strong>Items:</strong> ${order.items ? order.items.length : 0}</p>
                </div>
                <div class="order-actions">
                    <a href="order_detail.html?id=${order.id}" class="btn btn-secondary">View Details</a>
                </div>
            </div>
        `).join('');

        list.innerHTML = html;

    } catch (e) {
        console.error("Orders Load Error:", e);
        list.innerHTML = '<h2 class="content-title">Order History</h2><p class="error">Failed to load orders.</p>';
    }
}

// --- EXISTING FUNCTIONS (UNCHANGED) ---

async function loadAddresses() {
    const list = document.querySelector('.address-list');
    if(!list) return;
    
    list.innerHTML = '<div style="text-align:center; padding:10px; color:#666;">Loading addresses...</div>';

    try {
        const response = await apiCall('/auth/customer/addresses/', 'GET', null, true);
        
        let addresses = [];
        if (response && Array.isArray(response.results)) {
            addresses = response.results;
        } else if (Array.isArray(response)) {
            addresses = response;
        }

        list.innerHTML = '';

        if(addresses.length === 0) {
            list.innerHTML = '<p style="color:#777; text-align:center; padding: 20px;">No saved addresses found. Add one now!</p>';
            return;
        }

        addresses.forEach(addr => {
            const div = document.createElement('div');
            div.className = `address-card-profile ${addr.is_default ? 'default' : ''}`;
            div.innerHTML = `
                ${addr.is_default ? '<span class="default-badge"><i class="fas fa-check-circle"></i> Default</span>' : ''}
                <span class="address-tag">${addr.address_type}</span>
                <h4 class="address-name">${addr.city} - ${addr.pincode}</h4>
                <p class="address-full">${addr.full_address}</p>
                <div class="address-actions">
                    <button class="btn-icon btn-danger" onclick="deleteAddress('${addr.id}')">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                    ${!addr.is_default ? 
                        `<button class="btn-icon" onclick="setDefaultAddress('${addr.id}')"><i class="fas fa-check"></i> Set Default</button>` 
                        : ''}
                </div>
            `;
            list.appendChild(div);
        });

    } catch (e) {
        console.error("Address Load Error:", e);
        list.innerHTML = `<p class="error" style="color:red; text-align:center;">Failed to load addresses.</p>`;
    }
}

async function handleAddressSubmit(e) {
    e.preventDefault();
    console.log("Saving address...");
    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = "Saving...";

    const payload = {
        full_address: document.getElementById('full-address').value,
        city: document.getElementById('city').value,
        pincode: document.getElementById('pincode').value,
        address_type: document.getElementById('address-type').value,
        lat: 12.9716, 
        lng: 77.5946,
        is_default: false
    };

    try {
        await apiCall('/auth/customer/addresses/', 'POST', payload, true);
        document.getElementById('address-modal').style.display = 'none';
        document.getElementById('address-form').reset();
        await loadAddresses();
        alert("Address saved successfully!");
    } catch (error) {
        alert("Failed to save: " + error.message);
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

function setupAddressModal() {
    const modal = document.getElementById('address-modal');
    const showBtn = document.getElementById('show-address-modal');
    const closeBtn = document.getElementById('close-address-modal');
    const form = document.getElementById('address-form');

    if(showBtn && modal) showBtn.onclick = () => modal.style.display = 'flex';
    if(closeBtn && modal) closeBtn.onclick = () => modal.style.display = 'none';
    
    window.onclick = (event) => {
        if (event.target == modal) modal.style.display = "none";
    }

    if(form) form.addEventListener('submit', handleAddressSubmit);
}

window.deleteAddress = async (id) => {
    if(!confirm("Delete this address?")) return;
    try {
        await apiCall(`/auth/customer/addresses/${id}/`, 'DELETE', null, true);
        await loadAddresses();
    } catch(e) { alert("Error: " + e.message); }
};

window.setDefaultAddress = async (id) => {
    try {
        await apiCall(`/auth/customer/addresses/${id}/set-default/`, 'POST', {}, true);
        await loadAddresses();
    } catch(e) { alert("Error: " + e.message); }
};