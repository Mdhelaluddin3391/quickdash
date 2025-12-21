/**
 * location_manager.js
 * RESPONSIBILITY: Manage Serviceability State ONLY.
 */

const LocationManager = {
    
    // Core Keys
    KEYS: {
        LAT: 'quickdash_lat',
        LNG: 'quickdash_lng',
        WH_ID: 'quickdash_warehouse_id'
    },

    init: function() {
        this.checkLocationState();
    },

    checkLocationState: function() {
        const whId = sessionStorage.getItem(this.KEYS.WH_ID);
        const isUnavailablePage = window.location.pathname.includes('service-unavailable');

        if (!whId && !isUnavailablePage) {
            // No location set, prompt user
            this.showLocationPrompt(); 
        } else if (whId && isUnavailablePage) {
            // User has valid location but is on error page -> send to Home
            window.location.href = '/';
        }
    },

    // Called when user selects Pin or allows GPS
    handleLocationInput: async function(lat, lng) {
        try {
            const response = await fetch('/api/v1/warehouse/check-serviceability/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken') // Ensure util exists
                },
                body: JSON.stringify({ lat: lat, lng: lng })
            });

            const data = await response.json();

            if (data.serviceable) {
                // SAVE TO SESSION
                sessionStorage.setItem(this.KEYS.LAT, lat);
                sessionStorage.setItem(this.KEYS.LNG, lng);
                sessionStorage.setItem(this.KEYS.WH_ID, data.warehouse_id);
                
                // RELOAD / GO HOME
                window.location.href = '/';
            } else {
                // BLOCK USER
                this.clearLocation();
                window.location.href = '/service-unavailable/';
            }

        } catch (error) {
            console.error("Service check failed", error);
            alert("Could not verify location. Please try again.");
        }
    },

    clearLocation: function() {
        sessionStorage.clear();
        // Also call backend logout if needed, or backend session clear endpoint
    },
    
    showLocationPrompt: function() {
        // Logic to trigger the Bootstrap Modal ID #locationModal
        const modal = new bootstrap.Modal(document.getElementById('locationModal'));
        modal.show();
    }
};

document.addEventListener('DOMContentLoaded', () => {
    LocationManager.init();
});