/**
 * QuickDash Location Manager
 * Handles:
 * 1. Bottom Sheet visibility (Cookies/LocalStorage)
 * 2. HTML5 Geolocation API
 * 3. Serviceability Check API
 * * Refactored to use standard apiCall and APP_CONFIG
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
        // 1. If we already have a location (checked via Global Config)
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
        if(this.sheet) this.sheet.style.bottom = '0';
        if(this.overlay) this.overlay.style.display = 'block';
    },

    close: function() {
        if(this.sheet) this.sheet.style.bottom = '-100%';
        if(this.overlay) this.overlay.style.display = 'none';
        // Remember that user closed it
        localStorage.setItem(this.config.storageKey, Date.now().toString());
    },

    requestUserLocation: function() {
        if (!navigator.geolocation) {
            alert("Geolocation is not supported by your browser.");
            return;
        }

        const btn = document.querySelector("button[onclick='requestUserLocation()']");
        const originalText = btn ? btn.innerHTML : 'Use Current Location';
        
        if(btn) btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Locating...';

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                this.verifyServiceability(lat, lng, btn, originalText);
            },
            (error) => {
                this.handleError(error);
                if(btn) btn.innerHTML = originalText;
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    },

    verifyServiceability: async function(lat, lng, btn, originalText) {
        try {
            // STANDARD API CALL (No more manual fetch/CSRF)
            // auth=true ensures we send Token if user is logged in
            const data = await apiCall('/location/check-serviceability/', 'POST', { lat, lng }, true);

            if (data.serviceable) {
                this.close();
                this.showToast(`Delivery available! ETA: ${data.eta_minutes} mins`, 'success');
                
                // If logged in, the backend likely saved it implicitly, or we explicitly save it
                if (window.APP_CONFIG && window.APP_CONFIG.IS_LOGGED_IN) {
                    await this.saveLocationToBackend(lat, lng);
                } else {
                    // Just reload to update store inventory based on session
                    setTimeout(() => window.location.reload(), 1000);
                }
            } else {
                this.close();
                // Use Centralized URL Configuration
                if(window.APP_CONFIG && window.APP_CONFIG.URLS) {
                    window.location.href = window.APP_CONFIG.URLS.NOT_SERVICEABLE;
                } else {
                    alert("Service not available in this area.");
                }
            }

        } catch (err) {
            console.error("Serviceability Check Failed", err);
            this.showToast(err.message || "Network error. Please try again.", 'error');
        } finally {
            if(btn) btn.innerHTML = originalText;
        }
    },

    saveLocationToBackend: async function(lat, lng) {
        try {
            await apiCall('/location/save-current/', 'POST', { lat, lng }, true);
            window.location.reload();
        } catch (e) {
            console.warn("Failed to save location to profile", e);
            // We reload anyway because session might be updated
            window.location.reload();
        }
    },

    handleError: function(error) {
        let msg = "Could not get location.";
        if (error.code === 1) msg = "Location permission denied.";
        else if (error.code === 2) msg = "Position unavailable.";
        else if (error.code === 3) msg = "Timeout retrieving location.";
        
        alert(msg);
        this.close();
    },

    showToast: function(msg, type) {
        // Use the global toast system if available, else fallback
        if (window.showToast) {
            window.showToast(msg, type);
        } else {
            alert(msg); 
        }
    }
};

// --- GLOBAL EXPORTS ---
// These are kept for HTML onclick compatibility
window.closeLocationPopup = () => LocationManager.close();

// NOTE: We do NOT export requestUserLocation here to avoid conflict with base.js.
// Phase 3 will resolve the collision properly. 
// For now, we only expose the Manager-specific one if specifically called.
window.LocationManager = LocationManager;

// Init on load
document.addEventListener('DOMContentLoaded', () => {
    LocationManager.init();
});