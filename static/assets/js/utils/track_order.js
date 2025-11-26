// assets/js/track_order.js

document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    const orderId = params.get('id');

    if(!orderId) {
        alert("No Order ID provided");
        return;
    }

    // 1. Load Order Details
    try {
        // Detail API endpoint shayad ViewSet mein default router se hai
        const order = await apiCall(`/orders/${orderId}/`, 'GET', null, true);
        document.querySelector('.order-id-title').innerText = `Order #${order.id.slice(0,8)}`;
        // Update timeline classes based on order.status...
    } catch (e) {
        console.error(e);
    }

    // 2. WebSocket Connection
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Port 8000 (Backend) par connect karna hai
    const socket = new WebSocket(`${wsProtocol}//127.0.0.1:8000/ws/order/track/${orderId}/?token=${localStorage.getItem('accessToken')}`);

    socket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        if(data.lat && data.lng) {
            // Map update logic here (Leaflet marker move)
            console.log("Rider Location:", data.lat, data.lng);
            // Agar map object global hai toh marker update karein
            if(window.riderMarker) {
                window.riderMarker.setLatLng([data.lat, data.lng]);
            }
        }
    };
});