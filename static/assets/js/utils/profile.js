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

    // 2. Load Data
    await loadOrders();
    await loadAddresses(); // <--- This function is fixed below

    // 3. Address Modal Toggles
    setupAddressModal();
});

async function loadAddresses() {
    const list = document.querySelector('.address-list');
    if(!list) return;
    
    list.innerHTML = '<div style="text-align:center; padding:10px;">Loading addresses...</div>';

    try {
        const response = await apiCall('/auth/customer/addresses/', 'GET', null, true);
        
        // [FIX] Explicitly handle Pagination (response.results) vs Flat Array
        const addresses = response.results ? response.results : response;

        list.innerHTML = '';

        if(!Array.isArray(addresses) || addresses.length === 0) {
            list.innerHTML = '<p style="color:#777; text-align:center;">No saved addresses found. Add one now!</p>';
            return;
        }

        addresses.forEach(addr => {
            const div = document.createElement('div');
            // Ensure CSS class matches profile_additions.css
            div.className = `address-card-profile ${addr.is_default ? 'default' : ''}`;
            
            div.innerHTML = `
                ${addr.is_default ? '<span class="default-badge"><i class="fas fa-check-circle"></i> Default</span>' : ''}
                <span class="address-tag">${addr.address_type}</span>
                <h4 class="address-name">${addr.city} - ${addr.pincode}</h4>
                <p class="address-full">${addr.full_address}</p>
                <div class="address-actions">
                    <button class="btn-icon" onclick="deleteAddress(${addr.id})">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                    ${!addr.is_default ? 
                        `<button class="btn-default" onclick="setDefaultAddress(${addr.id})">Set Default</button>` 
                        : ''}
                </div>
            `;
            list.appendChild(div);
        });

    } catch (e) {
        console.error("Address Load Error:", e);
        list.innerHTML = '<p class="error" style="color:red; text-align:center;">Failed to load addresses.</p>';
    }
}

async function handleAddressSubmit(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = "Saving...";

    // [NOTE] In a real app, use Geolocation API here. 
    // Sending hardcoded lat/lng for now to satisfy backend requirement.
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
        
        // Close modal
        document.getElementById('address-modal').style.display = 'none';
        document.getElementById('address-form').reset();
        
        // Refresh List
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
    if(form) form.addEventListener('submit', handleAddressSubmit);
}

// Global scope functions for onclick events
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