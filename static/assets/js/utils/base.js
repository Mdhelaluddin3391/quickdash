document.addEventListener('DOMContentLoaded', () => {
    initLocationWidget();
});

async function initLocationWidget() {
    const locText = document.getElementById('header-location');
    if (!locText) return;

    // 1. Check if User is Logged In & Has Default Address
    const user = APP_CONFIG.USER; // Loaded from base.html
    const token = localStorage.getItem('accessToken');

    if (token) {
        try {
            // Fetch default address
            const addresses = await apiCall('/auth/customer/addresses/');
            const defaultAddr = addresses.find(a => a.is_default) || addresses[0];

            if (defaultAddr && defaultAddr.latitude) {
                // User has address, calculate ETA
                updateNavbarWithETA(defaultAddr.latitude, defaultAddr.longitude, defaultAddr.city);
                return;
            }
        } catch (e) {
            console.warn("Could not fetch user address", e);
        }
    }

    // 2. Fallback: Browser GPS (Guest User)
    if (navigator.geolocation) {
        locText.innerText = "Locating...";
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const { latitude, longitude } = pos.coords;
                // Reverse Geocode Logic here or just show "Current Location"
                updateNavbarWithETA(latitude, longitude, "Current Location");
            },
            (err) => {
                locText.innerHTML = `<span style="cursor:pointer" onclick="window.location.href='/location_denied.html'">Enable Location</span>`;
            }
        );
    } else {
        locText.innerText = "Location Unavailable";
    }
}

async function updateNavbarWithETA(lat, lng, cityName) {
    const locText = document.getElementById('header-location');
    
    try {
        const response = await apiCall('/delivery/estimate/', 'POST', { lat, lng }, false); // Auth not mandatory for estimate
        
        if (response.serviceable) {
            locText.innerHTML = `
                <span style="font-weight:700; color:#32CD32;">${response.eta}</span> 
                <span style="color:#ccc;">•</span> 
                ${cityName}
            `;
        } else {
            locText.innerText = "Not Serviceable Area";
            locText.style.color = "red";
        }
    } catch (e) {
        locText.innerText = cityName || "Location Set";
    }
}