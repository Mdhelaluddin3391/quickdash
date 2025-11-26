document.addEventListener('DOMContentLoaded', () => {
    // --- 1. Map Initialization ---
    const mapContainer = document.getElementById('map');
    if(!mapContainer) return;

    // Default Location (Center)
    const defaultLocation = { lat: 12.9352, lng: 77.6160 };
    
    const map = L.map('map').setView([defaultLocation.lat, defaultLocation.lng], 14);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap'
    }).addTo(map);

    // --- 2. Icons ---
    const storeIcon = L.icon({
        iconUrl: 'https://cdn-icons-png.flaticon.com/512/3448/3448339.png',
        iconSize: [40, 40],
    });
    const customerIcon = L.icon({
        iconUrl: 'https://cdn-icons-png.flaticon.com/512/25/25694.png',
        iconSize: [35, 35],
    });
    const riderIcon = L.icon({
        iconUrl: 'https://cdn-icons-png.flaticon.com/512/3034/3034874.png',
        iconSize: [38, 38],
    });

    // --- 3. Logic from utils/track_order.js integration ---
    // Note: Since we are moving code, the logic to fetch order details 
    // and set up WebSocket is inside `assets/js/utils/track_order.js`.
    // We will allow that file to handle the dynamic markers.
    
    // Expose map and icons globally so utils script can use them
    window.trackingMap = map;
    window.icons = { store: storeIcon, customer: customerIcon, rider: riderIcon };
});