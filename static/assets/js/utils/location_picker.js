const LocationPicker = {
    // Configuration
    config: {
        defaultLat: 12.9716, // Fallback (Bangalore)
        defaultLng: 77.5946,
        apiEndpoints: {
            geocode: '/api/v1/location/geocode/', // Your Django Geocode Proxy
            save: '/api/v1/location/save-current/'
        },
        debounceTime: 600 // ms to wait after dragging stops
    },

    // State
    state: {
        lat: null,
        lng: null,
        mode: 'MANUAL', // 'AUTO' | 'MANUAL'
        address: '',
        isServiceable: false,
        timer: null // For debouncing
    },

    // Elements
    elements: {},
    map: null,

    init: function() {
        this.cacheDOM();
        this.bindEvents();
        // Don't load map immediately to save resources. Load on open.
    },

    cacheDOM: function() {
        this.elements = {
            modal: document.getElementById('location-modal'),
            closeBtn: document.getElementById('close-loc-modal'),
            gpsBtn: document.getElementById('btn-trigger-gps'),
            confirmBtn: document.getElementById('btn-confirm-location'),
            addressTitle: document.getElementById('loc-address-title'),
            addressText: document.getElementById('loc-address-text'),
            modeBadge: document.getElementById('loc-mode-badge'),
            modeText: document.getElementById('loc-mode-text'),
            errorMsg: document.getElementById('service-error')
        };
    },

    bindEvents: function() {
        this.elements.closeBtn.addEventListener('click', () => this.close());
        this.elements.gpsBtn.addEventListener('click', () => this.triggerGPS());
        this.elements.confirmBtn.addEventListener('click', () => this.confirmSelection());
    },

    open: function() {
        this.elements.modal.classList.remove('hidden');
        if (!this.map) {
            this.initMap(); // Initialize Leaflet only once
        }
        
        // Attempt to get current location automatically on first open
        if (!this.state.lat) {
            this.triggerGPS();
        }
    },

    close: function() {
        this.elements.modal.classList.add('hidden');
    },

    initMap: function() {
        // Initialize Leaflet Map
        this.map = L.map('picker-map', { zoomControl: false }).setView(
            [this.config.defaultLat, this.config.defaultLng], 13
        );

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap'
        }).addTo(this.map);

        // EVENT: When map is dragged
        this.map.on('move', () => {
            // UI Feedback that we are moving
            this.elements.confirmBtn.disabled = true;
            this.elements.addressTitle.innerText = "Locating...";
            this.elements.addressText.innerText = "Release to check availability";
            this.updateMode('MANUAL');
        });

        // EVENT: When map stops moving (The core logic)
        this.map.on('moveend', () => {
            const center = this.map.getCenter();
            
            // Debounce the API Call
            clearTimeout(this.state.timer);
            this.state.timer = setTimeout(() => {
                this.handleLocationUpdate(center.lat, center.lng);
            }, this.config.debounceTime);
        });
    },

    triggerGPS: function() {
        if (!navigator.geolocation) {
            alert("Geolocation not supported");
            return;
        }

        this.elements.gpsBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>'; // Loading icon

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const { latitude, longitude } = position.coords;
                this.updateMode('AUTO');
                
                // Fly to location (triggers moveend, which triggers API)
                this.map.flyTo([latitude, longitude], 17);
                this.elements.gpsBtn.innerHTML = '<i class="fas fa-crosshairs"></i>';
            },
            (error) => {
                console.error(error);
                alert("Could not detect location. Please select manually.");
                this.elements.gpsBtn.innerHTML = '<i class="fas fa-crosshairs"></i>';
            },
            { enableHighAccuracy: true }
        );
    },

    updateMode: function(mode) {
        this.state.mode = mode;
        this.elements.modeText.innerText = mode === 'AUTO' ? 'Using GPS' : 'Manual Pin';
        // Optional: Change badge color based on mode
    },

    // The "Brain" function that calls Backend
    handleLocationUpdate: async function(lat, lng) {
        this.state.lat = lat;
        this.state.lng = lng;

        try {
            // Call your Django Proxy API
            const response = await fetch(this.config.apiEndpoints.geocode, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: JSON.stringify({ lat, lng })
            });

            const data = await response.json();

            // Update State & UI
            this.state.address = data.address;
            this.state.isServiceable = data.is_serviceable;

            this.elements.addressTitle.innerText = data.components.area || "Selected Location";
            this.elements.addressText.innerText = data.address;

            if (data.is_serviceable) {
                this.elements.errorMsg.classList.add('hidden');
                this.elements.confirmBtn.disabled = false;
                this.elements.confirmBtn.innerText = "Confirm Location";
            } else {
                this.elements.errorMsg.classList.remove('hidden');
                this.elements.confirmBtn.disabled = true;
            }

        } catch (error) {
            console.error("Geocode Error", error);
            this.elements.addressTitle.innerText = "Error";
            this.elements.addressText.innerText = "Could not fetch address details.";
        }
    },

    confirmSelection: function() {
        // Save to backend
        fetch(this.config.apiEndpoints.save, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCookie('csrftoken')
            },
            body: JSON.stringify({
                lat: this.state.lat,
                lng: this.state.lng,
                address_text: this.state.address,
                selection_type: this.state.mode
            })
        }).then(res => {
            if(res.ok) {
                window.location.reload(); // Reload to refresh inventory/serviceability
            }
        });
    },

    getCookie: function(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
};

// Initialize on Load
document.addEventListener('DOMContentLoaded', () => {
    LocationPicker.init();
});