/**
 * QuickDash Location Manager
 * Handles:
 * 1. Bottom Sheet visibility (Cookies/LocalStorage)
 * 2. HTML5 Geolocation API
 * 3. Serviceability Check API
 */

const LocationManager = {
    config: {
        sheetId: 'location-bottom-sheet',
        overlayId: 'location-popup-overlay',
        storageKey: 'qd_loc_declined_ts', // Timestamp when user closed popup
        askInterval: 5 * 60 * 1000, // 5 Minutes
    },

    init: function() {
        this.sheet = document.getElementById(this.config.sheetId);
        this.overlay = document.getElementById(this.config.overlayId);
        
        if (!this.sheet) return;

        // Check if we should show the popup
        this.checkShouldShow();
    },

    checkShouldShow: function() {
        // 1. If we already have a location (checked via a cookie/global var set by Django)
        if (window.APP_CONFIG && window.APP_CONFIG.HAS_LOCATION) {
            return;
        }

        // 2. Check if user recently closed it
        const lastClosed = localStorage.getItem(this.config.storageKey);
        const now = Date.now();

        if (lastClosed && (now - parseInt(lastClosed)) < this.config.askInterval) {
            console.log("Location popup suppressed due to recent close.");
            return;
        }

        // 3. Show it
        this.show();
    },

    show: function() {
        this.sheet.style.bottom = '0';
        this.overlay.style.display = 'block';
    },

    close: function() {
        this.sheet.style.bottom = '-100%';
        this.overlay.style.display = 'none';
        // Remember that user closed it
        localStorage.setItem(this.config.storageKey, Date.now().toString());
    },

    requestUserLocation: function() {
        if (!navigator.geolocation) {
            alert("Geolocation is not supported by your browser.");
            return;
        }

        const btn = document.querySelector("button[onclick='requestUserLocation()']");
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Locating...';

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                this.verifyServiceability(lat, lng);
                btn.innerHTML = originalText;
            },
            (error) => {
                this.handleError(error);
                btn.innerHTML = originalText;
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    },

    verifyServiceability: function(lat, lng) {
        // Call Django API
        fetch('/api/v1/location/check-serviceability/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // Assuming you have a getCookie function for CSRF
                'X-CSRFToken': this.getCookie('csrftoken') 
            },
            body: JSON.stringify({ lat: lat, lng: lng })
        })
        .then(response => response.json())
        .then(data => {
            if (data.serviceable) {
                // Success!
                this.close();
                this.showToast(`Delivery available! ETA: ${data.eta_minutes} mins`, 'success');
                
                // If logged in, save this as "Current Location"
                if (window.APP_CONFIG && window.APP_CONFIG.IS_LOGGED_IN) {
                    this.saveLocationToBackend(lat, lng);
                } else {
                    // Just reload to update store inventory based on session
                    setTimeout(() => window.location.reload(), 1000);
                }
            } else {
                this.close();
                // Redirect to "Not Serviceable" page or show error
                window.location.href = '/templates/frontend/pages/not_serviceable.html';
            }
        })
        .catch(err => {
            console.error("API Error", err);
            this.showToast("Network error. Please try again.", 'error');
        });
    },

    saveLocationToBackend: function(lat, lng) {
        fetch('/api/v1/location/save-current/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                'X-CSRFToken': this.getCookie('csrftoken')
            },
            body: JSON.stringify({ lat: lat, lng: lng })
        })
        .then(() => {
            window.location.reload();
        });
    },

    handleError: function(error) {
        let msg = "Could not get location.";
        if (error.code === 1) msg = "Location permission denied.";
        else if (error.code === 2) msg = "Position unavailable.";
        else if (error.code === 3) msg = "Timeout retrieving location.";
        
        alert(msg);
        this.close();
    },

    // Helper for CSRF
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
    },

    showToast: function(msg, type) {
        // Assuming you have a toast library or use alert
        alert(msg); 
    }
};

// Expose to global scope for HTML onclick events
window.closeLocationPopup = () => LocationManager.close();
window.requestUserLocation = () => LocationManager.requestUserLocation();

// Init on load
document.addEventListener('DOMContentLoaded', () => {
    LocationManager.init();
});