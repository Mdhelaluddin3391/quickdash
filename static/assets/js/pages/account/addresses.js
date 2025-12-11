// static/assets/js/pages/account/addresses.js

document.addEventListener('DOMContentLoaded', () => {
    // Load existing addresses
    loadAddresses();

    // Attach Event Listener Safely
    const addForm = document.getElementById('add-addr-form');
    if (addForm) {
        addForm.addEventListener('submit', handleAddAddress);
    }
});

async function loadAddresses() {
    const grid = document.getElementById('address-grid');
    if(!grid) return;
    
    grid.innerHTML = '<div class="loader">Loading...</div>';

    try {
        // Correct URL: /api/v1/auth/customer/addresses/
        const response = await apiCall('/auth/customer/addresses/');
        
        // Handle DRF pagination (response.results) or flat list
        const addresses = Array.isArray(response) ? response : (response.results || []);

        grid.innerHTML = '';

        if(addresses.length === 0) {
            grid.innerHTML = '<p class="text-muted">No addresses saved.</p>';
            return;
        }

        addresses.forEach(a => {
            const div = document.createElement('div');
            div.className = 'addr-item';
            div.innerHTML = `
                <span class="addr-type">${a.address_type}</span>
                <h4>${a.city}</h4>
                <p class="text-muted mb-0">${a.full_address} - ${a.pincode}</p>
                <div class="addr-actions">
                    ${a.is_default ? '<span class="text-success text-sm"><i class="fas fa-check"></i> Default</span>' : 
                    `<button class="btn-link" onclick="setDefault('${a.id}')">Set Default</button>`}
                    <button class="btn-text-danger" onclick="deleteAddr('${a.id}')">Delete</button>
                </div>
            `;
            grid.appendChild(div);
        });

    } catch (e) {
        console.error("Load Error:", e);
        grid.innerHTML = '<p class="text-danger">Error loading addresses.</p>';
    }
}

async function handleAddAddress(e) {
    e.preventDefault();

    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerText;
    btn.innerText = "Saving...";
    btn.disabled = true;

    const addressTypeInput = document.querySelector('input[name="address_type"]:checked');
    const addressTypeValue = addressTypeInput ? addressTypeInput.value : 'HOME';

    const payload = {
        full_address: document.getElementById('a-line').value,
        city: document.getElementById('a-city').value,
        pincode: document.getElementById('a-pincode').value,
        address_type: addressTypeValue,
        lat: 12.9716, // Placeholder coordinates
        lng: 77.5946 
    };

    try {
        await apiCall('/auth/customer/addresses/', 'POST', payload);
        alert("Address Saved Successfully!");
        closeAddrModal();
        e.target.reset(); 
        loadAddresses(); 
    } catch(err) {
        console.error(err);
        alert("Error: " + err.message);
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
}

// Modal Logic
window.openAddressModal = function() { document.getElementById('addr-modal').style.display = 'flex'; }
window.closeAddrModal = function() { document.getElementById('addr-modal').style.display = 'none'; }

window.deleteAddr = async function(id) {
    if(!confirm("Are you sure?")) return;
    try {
        await apiCall(`/auth/customer/addresses/${id}/`, 'DELETE');
        loadAddresses();
    } catch (e) { alert(e.message); }
}

window.setDefault = async function(id) {
    try {
        await apiCall(`/auth/customer/addresses/${id}/set-default/`, 'POST');
        loadAddresses();
    } catch (e) { alert(e.message); }
}