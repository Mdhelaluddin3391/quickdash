let map, riderMarker;

document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    const orderId = params.get('id');

    if (!orderId) {
        alert("Invalid Order ID");
        window.location.href = '/orders.html';
        return;
    }

    document.getElementById('order-id-display').innerText = `Order #${orderId.slice(0,8).toUpperCase()}`;

    // 1. Initialize Map
    initMap();

    // 2. Connect WebSocket
    connectTracking(orderId);
});

function initMap() {
    // Default center (Bangalore) - Update based on your region
    map = L.map('map').setView([12.9716, 77.5946], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap'
    }).addTo(map);
}

function connectTracking(orderId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const token = localStorage.getItem('accessToken');
    
    const wsUrl = `${protocol}//${host}/ws/order/track/${orderId}/?token=${token}`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => console.log("Tracking Connected");
    
    socket.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.lat && data.lng) {
            updateRiderPosition(data.lat, data.lng);
        }
    };

    socket.onclose = () => console.log("Tracking Disconnected");
}

function updateRiderPosition(lat, lng) {
    if (!riderMarker) {
        const icon = L.icon({
            iconUrl: 'https://cdn-icons-png.flaticon.com/512/3034/3034874.png', // Rider Icon
            iconSize: [40, 40],
        });
        riderMarker = L.marker([lat, lng], {icon: icon}).addTo(map);
    } else {
        riderMarker.setLatLng([lat, lng]);
    }
    map.panTo([lat, lng]);
}