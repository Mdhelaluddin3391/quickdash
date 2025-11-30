// assets/js/utils/profile.js

document.addEventListener('DOMContentLoaded', async () => {
    if (!isLoggedIn()) window.location.href = 'auth.html';

    // 1. Load User Info
    const userStr = localStorage.getItem('user');
    if(userStr) {
        const user = JSON.parse(userStr);
        document.querySelector('.user-name').innerText = user.full_name || "Guest User";
        document.querySelector('.user-phone').innerText = user.phone || "";
        document.querySelector('.user-avatar').innerText = (user.full_name || "U").charAt(0).toUpperCase();
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
    container.innerHTML = '<h2 class="content-title">Order History</h2><div class="loading-spinner">Loading...</div>';

    try {
        const orders = await apiCall('/orders/', 'GET', null, true);
        
        container.innerHTML = '<h2 class="content-title">Order History</h2>'; // Clear loader

        if(orders.length === 0) {
            container.innerHTML += '<p>No orders yet.</p>';
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
                    <p><strong>Items:</strong> ${order.items.length} items</p>
                    <p><strong>Total:</strong> ₹${order.final_amount}</p>
                    <p><strong>Date:</strong> ${date}</p>
                </div>
                <div class="order-actions">
                    <a href="track_order.html?id=${order.id}" class="btn btn-primary">Track Order</a>
                    ${order.status === 'delivered' ? '<a href="#" class="btn btn-secondary">Invoice</a>' : ''}
                </div>
            `;
            container.appendChild(div);
        });

    } catch (e) {
        console.error(e);
        container.innerHTML = '<h2 class="content-title">Order History</h2><p class="error">Failed to load orders.</p>';
    }
}

async function loadAddresses() {
    const list = document.querySelector('.address-list');
    list.innerHTML = '<p>Loading addresses...</p>';

    try {
        const addresses = await apiCall('/auth/customer/addresses/', 'GET', null, true);
        list.innerHTML = '';

        if(addresses.length === 0) {
            list.innerHTML = '<p>No saved addresses.</p>';
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
        console.error(e);
        list.innerHTML = '<p class="error">Failed to load addresses.</p>';
    }
}

async function handleAddressSubmit(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = "Saving...";

    // 1. Simulate Geocoding (In production, use Google Maps API)
    // We generate a random point near Bangalore for demo purposes if backend validation is strict
    // Ideally, you use navigator.geolocation.getCurrentPosition here.
    const mockLat = 12.97 + (Math.random() * 0.01); 
    const mockLng = 77.59 + (Math.random() * 0.01);

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
        
        // Close modal
        document.getElementById('address-modal').style.display = 'none';
        document.getElementById('address-form').reset();
        
        // Refresh List
        await loadAddresses();
        alert("Address saved successfully!");

    } catch (error) {
        alert("Failed to save address: " + error.message);
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

// Global functions for inline onclick events
window.deleteAddress = async (id) => {
    if(!confirm("Are you sure?")) return;
    try {
        await apiCall(`/auth/customer/addresses/${id}/`, 'DELETE', null, true);
        await loadAddresses();
    } catch(e) { alert("Delete failed"); }
};

window.setDefaultAddress = async (id) => {
    try {
        await apiCall(`/auth/customer/addresses/${id}/set-default/`, 'POST', {}, true);
        await loadAddresses();
    } catch(e) { alert("Update failed"); }
};