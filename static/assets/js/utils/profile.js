// assets/js/utils/profile.js

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

    // 2. Load Sections
    await loadOrders();
    await loadAddresses();

    // 3. Logout Handler
    const logoutLink = document.querySelector('.logout-link');
    if(logoutLink) {
        logoutLink.addEventListener('click', (e) => {
            e.preventDefault();
            logout();
        });
    }

    // 4. Address Form Handler
    const addressForm = document.getElementById('address-form');
    if(addressForm) {
        addressForm.addEventListener('submit', handleAddressSubmit);
    }
});

async function loadOrders() {
    const container = document.getElementById('orders');
    if(!container) return;
    
    container.innerHTML = '<h2 class="content-title">Order History</h2><div style="padding:20px; text-align:center;">Loading...</div>';

    try {
        // Handle pagination: response might be array or {results: []}
        const response = await apiCall('/orders/', 'GET', null, true);
        const orders = response.results || response; // FIX: Handle Paginated Response
        
        container.innerHTML = '<h2 class="content-title">Order History</h2>'; 

        if(!orders || orders.length === 0) {
            container.innerHTML += '<p style="color:#777;">No orders placed yet.</p>';
            return;
        }

        orders.forEach(order => {
            const date = new Date(order.created_at).toLocaleDateString();
            const statusClass = order.status === 'delivered' ? 'completed' : 'pending';
            
            const div = document.createElement('div');
            div.className = `order-card ${statusClass}`;
            div.innerHTML = `
                <div class="order-header">
                    <span class="order-id">#${order.id.slice(0,8).toUpperCase()}</span>
                    <span class="order-status">${order.status.toUpperCase()}</span>
                </div>
                <div class="order-details">
                    <p><strong>Items:</strong> ${order.items ? order.items.length : 0} items</p>
                    <p><strong>Total:</strong> ₹${order.final_amount}</p>
                    <p><strong>Date:</strong> ${date}</p>
                </div>
                <div class="order-actions">
                    <a href="track_order.html?id=${order.id}" class="btn btn-primary">Track Order</a>
                </div>
            `;
            container.appendChild(div);
        });

    } catch (e) {
        console.error("Orders Load Error:", e);
        container.innerHTML = '<h2 class="content-title">Order History</h2><p class="error">Could not load orders.</p>';
    }
}

async function loadAddresses() {
    const list = document.querySelector('.address-list');
    if(!list) return;
    
    list.innerHTML = '<p>Loading addresses...</p>';

    try {
        const response = await apiCall('/auth/customer/addresses/', 'GET', null, true);
        // [CRITICAL FIX] Handle pagination results
        const addresses = response.results || response;

        list.innerHTML = '';

        if(!Array.isArray(addresses) || addresses.length === 0) {
            list.innerHTML = '<p style="color:#777;">No saved addresses found.</p>';
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
                    <button class="btn-icon" onclick="deleteAddress(${addr.id})"><i class="fas fa-trash"></i> Delete</button>
                    ${!addr.is_default ? `<button class="btn-default" onclick="setDefaultAddress(${addr.id})">Set Default</button>` : ''}
                </div>
            `;
            list.appendChild(div);
        });

    } catch (e) {
        console.error("Address Load Error:", e);
        list.innerHTML = '<p class="error">Failed to load addresses. Please check connection.</p>';
    }
}

async function handleAddressSubmit(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = "Saving...";

    // Mock Coordinates for now (Real app should use GPS)
    const mockLat = 12.9716; 
    const mockLng = 77.5946;

    const payload = {
        full_address: document.getElementById('full-address').value,
        city: document.getElementById('city').value,
        pincode: document.getElementById('pincode').value,
        address_type: document.getElementById('address-type').value,
        lat: mockLat, 
        lng: mockLng
    };

    try {
        await apiCall('/auth/customer/addresses/', 'POST', payload, true);
        
        // Close modal and reset
        const modal = document.getElementById('address-modal');
        if(modal) modal.style.display = 'none';
        document.getElementById('address-form').reset();
        
        // Refresh List immediately
        await loadAddresses();
        alert("Address saved successfully!");

    } catch (error) {
        console.error("Save Address Error:", error);
        alert("Failed to save address: " + error.message);
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

// Global functions for inline HTML events
window.deleteAddress = async (id) => {
    if(!confirm("Are you sure you want to delete this address?")) return;
    try {
        await apiCall(`/auth/customer/addresses/${id}/`, 'DELETE', null, true);
        await loadAddresses();
    } catch(e) { alert("Delete failed: " + e.message); }
};

window.setDefaultAddress = async (id) => {
    try {
        await apiCall(`/auth/customer/addresses/${id}/set-default/`, 'POST', {}, true);
        await loadAddresses();
    } catch(e) { alert("Update failed: " + e.message); }
};