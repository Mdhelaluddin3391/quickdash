// static/assets/js/pages/admin/dashboard.js

document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    loadProfile();
});

// --- 1. Authentication ---
function checkAuth() {
    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/admin-panel/login/';
    }
}

function loadProfile() {
    const userStr = localStorage.getItem('user');
    if (userStr) {
        const user = JSON.parse(userStr);
        document.getElementById('admin-name').innerText = user.full_name || "Admin";
        // Optional: Check role here
    }
}

function logoutAdmin() {
    localStorage.clear();
    window.location.href = '/admin-panel/login/';
}

// --- 2. Navigation ---
function showSection(sectionId, navElement) {
    // Hide all sections
    document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
    // Show target section
    document.getElementById(`section-${sectionId}`).classList.add('active');
    
    // Update Title
    document.getElementById('page-title').innerText = navElement.innerText.trim();

    // Update Sidebar Active State
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    navElement.classList.add('active');

    // Load Data if needed
    if (sectionId === 'catalog') loadProducts();
    if (sectionId === 'orders') loadOrders();
}

// --- 3. Catalog & Bulk Upload ---
function toggleUploadBox() {
    const box = document.getElementById('bulk-upload-box');
    box.style.display = box.style.display === 'none' ? 'block' : 'none';
}

async function uploadCSV() {
    const fileInput = document.getElementById('csvInput');
    const statusDiv = document.getElementById('upload-status');
    const file = fileInput.files[0];

    if (!file) {
        alert("Please select a CSV file");
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    statusDiv.innerHTML = '<span class="text-primary">Uploading...</span>';

    try {
        const token = localStorage.getItem('accessToken');
        const response = await fetch('/api/v1/catalog/import/bulk-csv/', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            statusDiv.innerHTML = `<span class="text-success">✅ ${data.message}</span>`;
            loadProducts(); // Refresh table
            setTimeout(() => toggleUploadBox(), 3000);
        } else {
            statusDiv.innerHTML = `<span class="text-danger">❌ ${data.error || 'Upload failed'}</span>`;
        }

    } catch (e) {
        console.error(e);
        statusDiv.innerHTML = '<span class="text-danger">Network Error</span>';
    }
}

async function loadProducts() {
    const tbody = document.getElementById('product-table-body');
    tbody.innerHTML = '<tr><td colspan="5">Loading...</td></tr>';

    try {
        const response = await apiCall('/catalog/skus/');
        const products = response.results || response;

        tbody.innerHTML = products.map(p => `
            <tr>
                <td>${p.sku_code}</td>
                <td>${p.name}</td>
                <td>${p.category_name || '-'}</td>
                <td>₹${p.sale_price}</td>
                <td>
                    <span class="badge bg-${p.is_active ? 'success' : 'secondary'}">
                        ${p.is_active ? 'Active' : 'Inactive'}
                    </span>
                </td>
            </tr>
        `).join('');
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-danger">Failed to load products</td></tr>';
    }
}

// --- 4. Orders Logic ---
async function loadOrders() {
    const container = document.getElementById('orders-container');
    const loader = document.getElementById('orders-loading');
    
    loader.style.display = 'block';
    container.innerHTML = '';

    try {
        const response = await apiCall('/orders/');
        const orders = response.results || response;
        loader.style.display = 'none';

        if(orders.length === 0) {
            container.innerHTML = '<p class="text-muted">No orders found.</p>';
            return;
        }

        // Simple Table for Orders
        let html = `<table class="table table-hover"><thead><tr><th>Order ID</th><th>Status</th><th>Amount</th><th>Time</th></tr></thead><tbody>`;
        
        orders.forEach(o => {
            html += `
                <tr>
                    <td>#${o.id.slice(0,8).toUpperCase()}</td>
                    <td><span class="badge bg-info">${o.status}</span></td>
                    <td>₹${o.final_amount}</td>
                    <td>${new Date(o.created_at).toLocaleString()}</td>
                </tr>
            `;
        });
        html += '</tbody></table>';
        container.innerHTML = html;

    } catch (e) {
        loader.style.display = 'none';
        container.innerHTML = '<p class="text-danger">Failed to fetch orders.</p>';
    }
}