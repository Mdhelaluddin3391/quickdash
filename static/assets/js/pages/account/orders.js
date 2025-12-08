// Orders Page State Management
let allOrders = [];
let currentPage = 1;
const itemsPerPage = 10;

document.addEventListener('DOMContentLoaded', async () => {
    try {
        await loadAllOrders();
    } catch (e) {
        console.error("Orders Load Error", e);
        showError("Failed to load orders", 3000);
    }
});

async function loadAllOrders() {
    const ordersResp = await apiCall('/orders/', 'GET', null, true);
    // Handle paginated or non-paginated response
    allOrders = Array.isArray(ordersResp) ? ordersResp : (ordersResp.results || []);
    
    // Sort orders by date (newest first)
    allOrders.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    
    // Display first page
    currentPage = 1;
    displayOrdersPage();
}

function displayOrdersPage() {
    const list = document.getElementById('orders-list');
    const noOrdersState = document.getElementById('no-orders');
    const paginationControls = document.getElementById('pagination-controls');

    // Handle empty state
    if (!allOrders || allOrders.length === 0) {
        list.innerHTML = '';
        noOrdersState.style.display = 'block';
        paginationControls.style.display = 'none';
        return;
    }

    noOrdersState.style.display = 'none';

    // Calculate pagination
    const totalPages = Math.ceil(allOrders.length / itemsPerPage);
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const paginatedOrders = allOrders.slice(startIndex, endIndex);

    // Render orders for current page
    list.innerHTML = '';
    paginatedOrders.forEach(o => {
        const date = new Date(o.created_at).toLocaleDateString('en-IN', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
        const statusClass = `status-${o.status.toLowerCase()}`;
        const itemCount = o.items ? o.items.reduce((sum, item) => sum + (item.quantity || 1), 0) : 0;

        const div = document.createElement('div');
        div.className = 'order-card';
        div.innerHTML = `
            <div class="o-info">
                <h4>Order #${o.id.slice(0,8).toUpperCase()}</h4>
                <p class="o-meta">${date} • ${itemCount} item${itemCount !== 1 ? 's' : ''} • ₹${parseFloat(o.final_amount).toFixed(2)}</p>
            </div>
            <div style="display:flex; gap:10px; align-items:center;">
                <span class="o-status ${statusClass}">${o.status}</span>
                <a href="/track_order.html?id=${o.id}" class="btn-sm btn-outline">View</a>
            </div>
        `;
        list.appendChild(div);
    });

    // Update pagination controls
    if (totalPages > 1) {
        paginationControls.style.display = 'flex';
        document.getElementById('page-info').innerText = `Page ${currentPage} of ${totalPages}`;
        document.getElementById('prev-btn').disabled = currentPage === 1;
        document.getElementById('next-btn').disabled = currentPage === totalPages;
    } else {
        paginationControls.style.display = 'none';
    }
}

function nextPage() {
    const totalPages = Math.ceil(allOrders.length / itemsPerPage);
    if (currentPage < totalPages) {
        currentPage++;
        displayOrdersPage();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

function previousPage() {
    if (currentPage > 1) {
        currentPage--;
        displayOrdersPage();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}