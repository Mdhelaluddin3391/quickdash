// assets/js/utils/track_order.js

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Get Order ID from URL
    const params = new URLSearchParams(window.location.search);
    const orderId = params.get('id');

    if(!orderId) {
        alert("No Order ID provided");
        window.location.href = 'profile.html';
        return;
    }

    // 2. Load Order Details via API
    try {
        // '/orders/' endpoint returns list, detailed view logic depends on your router.
        // Assuming /orders/<id>/ exists based on router configuration
        const order = await apiCall(`/orders/${orderId}/`, 'GET', null, true);
        
        const titleEl = document.querySelector('.order-id-title');
        if(titleEl) titleEl.innerText = `Order #${order.id.slice(0,8).toUpperCase()}`;
        
        // Setup initial map if order has driver location or store location
        // (Assuming you have map setup logic here or in pages/track_order.js)

    } catch (e) {
        console.error("Failed to fetch order details", e);
    }

    // 3. Dynamic WebSocket Connection
    // [FIX] Automatically detect protocol (ws or wss) and host (IP:Port or Domain)
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host; // e.g. "127.0.0.1:8000" or "quickdash.com"
    
    const token = localStorage.getItem('accessToken');
    if (!token) return;

    const socketUrl = `${wsProtocol}//${wsHost}/ws/order/track/${orderId}/?token=${token}`;
    const socket = new WebSocket(socketUrl);

    socket.onopen = function() {
        console.log("Tracking Connected");
    };

    socket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        if(data.lat && data.lng) {
            console.log("Rider Location Update:", data.lat, data.lng);
            
            // UI Update: Move Marker
            // Ensure 'window.riderMarker' and 'window.trackingMap' are initialized in pages/track_order.js
            if(window.riderMarker) {
                window.riderMarker.setLatLng([data.lat, data.lng]);
                if(window.trackingMap) {
                    window.trackingMap.panTo([data.lat, data.lng]);
                }
            }
        }
    };

    socket.onclose = function() {
        console.log("Tracking Disconnected");
    };
    
    socket.onerror = function(err) {
        console.error("WebSocket Error:", err);
    };
});