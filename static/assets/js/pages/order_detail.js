document.addEventListener('DOMContentLoaded', () => {
    // 1. URL se order ID nikaalein (Real implementation)
    const params = new URLSearchParams(window.location.search);
    // const orderId = params.get('id') || "QD1209384"; // Fallback for demo
    const orderId = "QD1209384"; // Currently dummy based on your HTML

    // 2. "Reorder" button logic
    const reorderBtn = document.getElementById('reorder-btn');
    if(reorderBtn) {
        reorderBtn.addEventListener('click', () => {
            reorderBtn.disabled = true;
            reorderBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
            
            // Backend API Simulation
            setTimeout(() => {
                alert('Items added to your cart!');
                window.location.href = 'cart.html';
            }, 1000);
        });
    }

    // 3. (Optional) Fetch Order Details from API
    // async function fetchOrderDetails() {
    //     try {
    //         const order = await apiCall(`/orders/${orderId}/`);
    //         // Update DOM elements here...
    //     } catch(e) { console.error(e); }
    // }
    // fetchOrderDetails();
});