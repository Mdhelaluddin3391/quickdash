function renderOrderDetails(order) {
    // Items
    const itemsList = document.getElementById('order-items-list');
    if (order.items && order.items.length > 0) {
        itemsList.innerHTML = order.items.map(item =>
            `<div class="order-item-row">
                <span>${item.quantity} x ${item.sku_name_snapshot}</span>
                <span>₹${parseFloat(item.total_price).toFixed(2)}</span>
            </div>`
        ).join('');
    } else {
        itemsList.innerHTML = '<span class="text-muted">No items</span>';
    }

    // Total
    document.getElementById('order-total').innerText = `₹${parseFloat(order.final_amount).toFixed(2)}`;

    // Payment
    let payment = order.payment_status ? order.payment_status : 'N/A';
    document.getElementById('order-payment').innerText = payment;

    // Address
    let addr = '';
    if (order.delivery_address_json && order.delivery_address_json.address) {
        addr = order.delivery_address_json.address;
    } else if (order.delivery_lat && order.delivery_lng) {
        addr = `Lat: ${order.delivery_lat}, Lng: ${order.delivery_lng}`;
    }
    document.getElementById('order-address-text').innerText = addr;
}

let map, riderMarker, addressMarker;

// Google Maps callback
window.initMap = async function() {
    const params = new URLSearchParams(window.location.search);
    const orderId = params.get('id');

    if (!orderId) {
        alert("Invalid Order ID");
        window.location.href = '/orders.html';
        return;
    }

    document.getElementById('order-id-display').innerText = `Order #${orderId.slice(0,8).toUpperCase()}`;

    // 1. Fetch order details
    let order = null;
    try {
        order = await apiCall(`/orders/${orderId}/`);
    } catch (e) {
        alert("Failed to load order details");
        return;
    }


    // 2. Render timeline/status dynamically
    renderTimeline(order);

    // 2b. Render order items, payment, and address
    renderOrderDetails(order);

    // 3. Initialize Google Map (default center: India)
    map = new google.maps.Map(document.getElementById('map'), {
        center: { lat: 22.9734, lng: 78.6569 },
        zoom: 13,
        styles: [
            { elementType: 'geometry', stylers: [{ color: '#f5f5f5' }] },
            { elementType: 'labels.icon', stylers: [{ visibility: 'off' }] },
            { elementType: 'labels.text.fill', stylers: [{ color: '#616161' }] },
            { elementType: 'labels.text.stroke', stylers: [{ color: '#f5f5f5' }] },
            { featureType: 'administrative.land_parcel', elementType: 'labels.text.fill', stylers: [{ color: '#bdbdbd' }] },
            { featureType: 'poi', elementType: 'geometry', stylers: [{ color: '#eeeeee' }] },
            { featureType: 'poi', elementType: 'labels.text.fill', stylers: [{ color: '#757575' }] },
            { featureType: 'poi.park', elementType: 'geometry', stylers: [{ color: '#e5e5e5' }] },
            { featureType: 'poi.park', elementType: 'labels.text.fill', stylers: [{ color: '#9e9e9e' }] },
            { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#ffffff' }] },
            { featureType: 'road.arterial', elementType: 'labels.text.fill', stylers: [{ color: '#757575' }] },
            { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#dadada' }] },
            { featureType: 'road.highway', elementType: 'labels.text.fill', stylers: [{ color: '#616161' }] },
            { featureType: 'road.local', elementType: 'labels.text.fill', stylers: [{ color: '#9e9e9e' }] },
            { featureType: 'transit.line', elementType: 'geometry', stylers: [{ color: '#e5e5e5' }] },
            { featureType: 'transit.station', elementType: 'geometry', stylers: [{ color: '#eeeeee' }] },
            { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#c9c9c9' }] },
            { featureType: 'water', elementType: 'labels.text.fill', stylers: [{ color: '#9e9e9e' }] }
        ]
    });


    // 4. Geocode delivery address and show marker
    let address = '';
    if (order.delivery_address_json && order.delivery_address_json.address) {
        address = order.delivery_address_json.address;
    }
    let deliveryLatLng = null;
    if (order.delivery_lat && order.delivery_lng) {
        deliveryLatLng = { lat: parseFloat(order.delivery_lat), lng: parseFloat(order.delivery_lng) };
        showAddressMarker(order.delivery_lat, order.delivery_lng, address);
    } else if (address) {
        geocodeAddress(address, (lat, lng) => {
            deliveryLatLng = { lat, lng };
            showAddressMarker(lat, lng, address);
            tryDrawRoute();
        });
    }

    // 4b. Draw route if warehouse and delivery coordinates are available
    let warehouseLatLng = null;
    if (order.warehouse_lat && order.warehouse_lng) {
        warehouseLatLng = { lat: parseFloat(order.warehouse_lat), lng: parseFloat(order.warehouse_lng) };
    }
    function tryDrawRoute() {
        if (warehouseLatLng && deliveryLatLng) {
            drawRoute(warehouseLatLng, deliveryLatLng);
        }
    }
    if (warehouseLatLng && deliveryLatLng) {
        drawRoute(warehouseLatLng, deliveryLatLng);
    }

    // 5. Connect WebSocket for live rider tracking
    connectTracking(orderId);
}

function geocodeAddress(address) {
    const geocoder = new google.maps.Geocoder();
    geocoder.geocode({ address: address }, (results, status) => {
        if (status === 'OK' && results[0]) {
            const loc = results[0].geometry.location;
            showAddressMarker(loc.lat(), loc.lng(), address);
        } else {
            console.warn('Geocode failed:', status);
        }
    });
}

function showAddressMarker(lat, lng, address) {
    if (addressMarker) addressMarker.setMap(null);
    addressMarker = new google.maps.Marker({
        position: { lat: parseFloat(lat), lng: parseFloat(lng) },
        map: map,
        icon: 'https://cdn-icons-png.flaticon.com/512/684/684908.png', // Home/Pin icon
        title: address || 'Delivery Address'
    });
    map.setCenter({ lat: parseFloat(lat), lng: parseFloat(lng) });
}

function connectTracking(orderId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const token = localStorage.getItem('accessToken');
    const wsUrl = `${protocol}//${host}/ws/order/track/${orderId}/?token=${token}`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => console.log('Tracking Connected');
    socket.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.lat && data.lng) {
            updateRiderPosition(data.lat, data.lng);
        }
    };
    socket.onclose = () => console.log('Tracking Disconnected');
}

function updateRiderPosition(lat, lng) {
    if (!riderMarker) {
        riderMarker = new google.maps.Marker({
            position: { lat: parseFloat(lat), lng: parseFloat(lng) },
            map: map,
            icon: 'https://cdn-icons-png.flaticon.com/512/3034/3034874.png', // Rider Icon
            title: 'Rider Location'
        });
    } else {
        riderMarker.setPosition({ lat: parseFloat(lat), lng: parseFloat(lng) });
    }
    map.panTo({ lat: parseFloat(lat), lng: parseFloat(lng) });
}

function renderTimeline(order) {
    // Example: update status steps based on order.timeline or order.status
    const steps = [
        { id: 'step-confirmed', status: 'CONFIRMED' },
        { id: 'step-packed', status: 'PACKED' },
        { id: 'step-dispatched', status: 'DISPATCHED' },
        { id: 'step-delivered', status: 'DELIVERED' }
    ];
    let currentIdx = steps.findIndex(s => s.status === order.status);
    if (currentIdx === -1) currentIdx = 0;
    steps.forEach((step, idx) => {
        const el = document.getElementById(step.id);
        if (!el) return;
        el.classList.remove('active');
        if (idx <= currentIdx) el.classList.add('active');
    });
    // Optionally, update rider info, timestamps, etc.
    if (order.rider_name) {
        document.getElementById('rider-info').innerText = order.rider_name;
    }
}