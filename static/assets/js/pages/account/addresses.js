/* static/assets/js/pages/account/addresses.js */

document.addEventListener('DOMContentLoaded', () => {
    loadAddresses();
});

// 1. Load Addresses from Backend
async function loadAddresses() {
    const grid = document.getElementById('address-grid');
    if(!grid) return;
    
    grid.innerHTML = '<div class="loader">Loading addresses...</div>';

    try {
        // API Call
        const response = await apiCall('/auth/customer/addresses/');
        // Handle pagination or flat list
        const addresses = Array.isArray(response) ? response : (response.results || []);

        grid.innerHTML = '';

        if(addresses.length === 0) {
            grid.innerHTML = `
                <div class="text-center p-4" style="width:100%">
                    <p class="text-muted">No addresses saved yet.</p>
                    <button class="btn btn-primary btn-sm" onclick="openAddressModal()">
                        <i class="fas fa-map-marker-alt"></i> Add New Address
                    </button>
                </div>`;
            return;
        }

        addresses.forEach(a => {
            const div = document.createElement('div');
            div.className = 'addr-item';
            // Styling the card
            div.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="badge bg-light text-dark border">${a.address_type}</span>
                    ${a.is_default ? '<span class="text-success small"><i class="fas fa-check-circle"></i> Default</span>' : ''}
                </div>
                <h5 class="mb-1">${a.city}</h5>
                <p class="text-muted small mb-3" style="min-height: 40px;">
                    ${a.full_address} <br> 
                    <strong>PIN: ${a.pincode}</strong>
                </p>
                <div class="addr-actions d-flex gap-2">
                    ${!a.is_default ? 
                        `<button class="btn btn-sm btn-outline-primary flex-fill" onclick="setDefault('${a.id}')">Make Default</button>` 
                        : '<button class="btn btn-sm btn-success disabled flex-fill">Active</button>'}
                    
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteAddr('${a.id}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
            grid.appendChild(div);
        });

    } catch (e) {
        console.error("Load Error:", e);
        grid.innerHTML = '<p class="text-danger">Failed to load addresses.</p>';
    }
}

// 2. Open Map Modal (Replaces old form logic)
window.openAddressModal = function() {
    // Check if the global LocationPicker is loaded
    if (window.LocationPicker) {
        window.LocationPicker.open();
    } else {
        alert("Location Service is initializing... please wait.");
    }
};

// 3. Delete Address
window.deleteAddr = async function(id) {
    if(!confirm("Are you sure you want to delete this address?")) return;
    try {
        await apiCall(`/auth/customer/addresses/${id}/`, 'DELETE');
        loadAddresses(); // Refresh list
    } catch (e) { 
        alert(e.message); 
    }
};

// 4. Set Default Address
window.setDefault = async function(id) {
    try {
        await apiCall(`/auth/customer/addresses/${id}/set-default/`, 'POST');
        loadAddresses(); // Refresh list
    } catch (e) { 
        alert(e.message); 
    }
};