document.addEventListener('DOMContentLoaded', loadAddresses);

async function loadAddresses() {
    const grid = document.getElementById('address-grid');
    grid.innerHTML = '<div class="loader">Loading...</div>';

    try {
        const addresses = await apiCall('/auth/customer/addresses/');
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
        grid.innerHTML = '<p class="text-danger">Error loading addresses.</p>';
    }
}

// Modal Logic
function openAddressModal() { document.getElementById('addr-modal').style.display = 'flex'; }
function closeAddrModal() { document.getElementById('addr-modal').style.display = 'none'; }

document.getElementById('add-addr-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
        full_address: document.getElementById('a-line').value,
        city: document.getElementById('a-city').value,
        pincode: document.getElementById('a-pincode').value,
        address_type: document.getElementById('a-type').value,
        lat: 12.9716, lng: 77.5946 // Hardcoded until Map Picker is added
    };

    try {
        await apiCall('/auth/customer/addresses/', 'POST', payload);
        closeAddrModal();
        loadAddresses();
    } catch(err) { alert(err.message); }
});

async function deleteAddr(id) {
    if(!confirm("Are you sure?")) return;
    await apiCall(`/auth/customer/addresses/${id}/`, 'DELETE');
    loadAddresses();
}

async function setDefault(id) {
    await apiCall(`/auth/customer/addresses/${id}/set-default/`, 'POST');
    loadAddresses();
}