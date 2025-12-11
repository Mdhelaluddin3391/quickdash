// static/assets/js/pages/account/track_order.js

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
    const mapEl = document.getElementById('map');
    if (mapEl && window.google) {
        map = new google.maps.Map(mapEl, {
            center: { lat: 12.9716, lng: 77.5946 }, // Bangalore Default
            zoom: 13,
            styles: [] // Keep default styles for simplicity
        });

        // 4. Geocode delivery address and show marker
        let address = '';
        if (order.delivery_address_json && order.delivery_address_json.full_address) {
            address = order.delivery_address_json.full_address;
        }
        
        let deliveryLatLng = null;
        if (order.delivery_lat && order.delivery_lng) {
            deliveryLatLng = { lat: parseFloat(order.delivery_lat), lng: parseFloat(order.delivery_lng) };
            showAddressMarker(order.delivery_lat, order.delivery_lng, address);
        } else if (address) {
            geocodeAddress(address, (lat, lng) => {
                deliveryLatLng = { lat, lng };
                showAddressMarker(lat, lng, address);
            });
        }
    }

    // 5. Connect WebSocket for live rider tracking
    connectTracking(orderId);
}

function geocodeAddress(address, callback) {
    if(!window.google) return;
    const geocoder = new google.maps.Geocoder();
    geocoder.geocode({ address: address }, (results, status) => {
        if (status === 'OK' && results[0]) {
            const loc = results[0].geometry.location;
            callback(loc.lat(), loc.lng());
        }
    });
}

function showAddressMarker(lat, lng, address) {
    if(!map) return;
    if (addressMarker) addressMarker.setMap(null);
    addressMarker = new google.maps.Marker({
        position: { lat: parseFloat(lat), lng: parseFloat(lng) },
        map: map,
        title: address || 'Delivery Address'
    });
    map.setCenter({ lat: parseFloat(lat), lng: parseFloat(lng) });
}

function connectTracking(orderId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    
    // [FIX] Correct Key: access_token
    const token = localStorage.getItem('access_token');
    
    if (!token) return;

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
    if(!map || !window.google) return;
    
    if (!riderMarker) {
        riderMarker = new google.maps.Marker({
            position: { lat: parseFloat(lat), lng: parseFloat(lng) },
            map: map,
            icon: {
                url: 'https://cdn-icons-png.flaticon.com/512/3034/3034874.png',
                scaledSize: new google.maps.Size(40, 40)
            },
            title: 'Rider Location'
        });
    } else {
        riderMarker.setPosition({ lat: parseFloat(lat), lng: parseFloat(lng) });
    }
}

function renderTimeline(order) {
    const steps = [
        { id: 'step-confirmed', status: 'CONFIRMED' },
        { id: 'step-packed', status: 'PACKED' },
        { id: 'step-dispatched', status: 'DISPATCHED' },
        { id: 'step-delivered', status: 'DELIVERED' }
    ];
    
    // Normalize status
    const currentStatus = (order.status || '').toUpperCase();
    
    // Find index
    let currentIdx = steps.findIndex(s => s.status === currentStatus);
    
    // Handle 'PENDING' or other statuses
    if (currentStatus === 'PENDING') currentIdx = -1; 
    
    steps.forEach((step, idx) => {
        const el = document.getElementById(step.id);
        if (!el) return;
        el.classList.remove('active');
        if (idx <= currentIdx) el.classList.add('active');
    });

    if (order.rider_name) {
        const riderInfo = document.getElementById('rider-info');
        if(riderInfo) riderInfo.innerText = `Rider: ${order.rider_name}`;
    }
}