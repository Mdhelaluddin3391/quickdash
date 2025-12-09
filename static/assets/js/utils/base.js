/* static/assets/js/utils/base.js */

document.addEventListener('DOMContentLoaded', () => {
    initLocationWidget();
    loadNavbarCategories(); 
    checkAndShowLocationPopup(); // New Function call
    if (window.updateGlobalCartCount) window.updateGlobalCartCount();
});

// --- NEW POPUP LOGIC ---
function checkAndShowLocationPopup() {
    // Check if user already dismissed it in this session or has a location set
    const dismissed = sessionStorage.getItem('location_popup_dismissed');
    const hasLocation = localStorage.getItem('user_lat') && localStorage.getItem('user_lng'); // Simple check idea
    
    // Agar location nahi hai aur popup dismiss nahi kiya hai, tab dikhao
    if (!dismissed && !hasLocation) {
        setTimeout(() => {
            const sheet = document.getElementById('location-bottom-sheet');
            const overlay = document.getElementById('location-popup-overlay');
            if (sheet && overlay) {
                sheet.style.bottom = '0';
                overlay.style.display = 'block';
            }
        }, 1500); // 1.5 second baad popup aayega
    }
}

function closeLocationPopup() {
    const sheet = document.getElementById('location-bottom-sheet');
    const overlay = document.getElementById('location-popup-overlay');
    
    if (sheet) sheet.style.bottom = '-100%';
    if (overlay) overlay.style.display = 'none';
    
    // Session mein save karein taaki refresh karne par baar baar na aye
    sessionStorage.setItem('location_popup_dismissed', 'true');
}

window.requestUserLocation = function() {
    if (navigator.geolocation) {
        closeLocationPopup(); // Popup band karein process start hone par
        const locText = document.getElementById('header-location');
        if(locText) locText.innerText = "Locating...";
        
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const { latitude, longitude } = pos.coords;
                // Save locally for UI checks
                localStorage.setItem('user_lat', latitude);
                localStorage.setItem('user_lng', longitude);
                
                checkServiceabilityAndRedirect(latitude, longitude, "Current Location");
            },
            (err) => {
                alert("Location access denied. Please enable it manually.");
            }
        );
    } else {
        alert("Geolocation is not supported by this browser.");
    }
};

// --- EXISTING FUNCTIONS (UPDATED) ---

async function loadNavbarCategories() {
    // ... (Same as before) ...
    const nav = document.getElementById('dynamic-navbar');
    if (!nav) return;
    try {
        const response = await apiCall('/catalog/categories/?page_size=100', 'GET', null, false);
        const allCategories = response.results || response;
        const parentCategories = allCategories.filter(c => !c.parent);
        parentCategories.forEach(cat => {
            const link = document.createElement('a');
            link.href = `/search_results.html?slug=${cat.slug}`;
            link.className = 'nav-item';
            link.innerText = cat.name;
            const currentSlug = new URLSearchParams(window.location.search).get('slug');
            if (currentSlug === cat.slug) link.classList.add('active');
            nav.appendChild(link);
        });
    } catch (error) { console.error("Navbar Error", error); }
}

async function initLocationWidget() {
    const locText = document.getElementById('header-location');
    if (!locText) return;

    const token = localStorage.getItem('access_token'); // BUG FIX: Correct key

    if (token) {
        try {
            const response = await apiCall('/auth/customer/addresses/');
            const addresses = response.results || response;
            const defaultAddr = addresses.find(a => a.is_default) || addresses[0];

            if (defaultAddr && defaultAddr.latitude) {
                if(document.getElementById('current-city-display')) {
                    document.getElementById('current-city-display').innerText = defaultAddr.city;
                }
                checkServiceabilityAndRedirect(defaultAddr.latitude, defaultAddr.longitude, defaultAddr.city);
                return;
            }
        } catch (e) {
            console.warn("Address fetch failed", e);
        }
    }
    
    // Logged in nahi hai ya address nahi hai, toh kuch mat karo (Popup sambhal lega)
    // Guest GPS logic ko 'requestUserLocation' function mein shift kar diya hai
}

async function checkServiceabilityAndRedirect(lat, lng, cityName) {
    const locText = document.getElementById('header-location');
    
    try {
        const response = await apiCall('/delivery/estimate/', 'POST', { lat, lng }, false);

        // *** FIX: Removed Forced Redirect ***
        // Ab hum user ko redirect nahi karenge, bas header mein status dikhayenge

        if (!response.serviceable) {
            if(locText) {
                locText.innerHTML = `<span style="color:red; font-weight:bold;">Not Serviceable</span> • ${cityName}`;
            }
            // Optional: Show a small toast notification instead of full page redirect
            if(window.showError) showError(`Sorry, we don't deliver to ${cityName} yet.`);
        } else {
            if(locText) {
                locText.innerHTML = `
                    <span style="font-weight:700; color:#32CD32;">${response.eta}</span> 
                    <span style="color:#ccc;">•</span> 
                    ${cityName}
                `;
            }
        }

    } catch (e) {
        console.error("Service Check Error", e);
        if(locText) locText.innerText = cityName || "Location Set";
    }
}

// --- Cart Count Global Helper ---
window.updateGlobalCartCount = async function () {
    const badge = document.getElementById('nav-cart-count');
    if (!badge) return;

    // [FIX] Sahi key 'access_token' use karein
    if (!localStorage.getItem('access_token')) {
        badge.innerText = '0';
        badge.style.display = 'none';
        return;
    }

    try {
        const cart = await apiCall('/orders/cart/');
        const count = cart.items ? cart.items.length : 0;

        badge.innerText = count;
        badge.style.display = count > 0 ? 'flex' : 'none';

        const pageBadge = document.getElementById('cart-count-badge');
        if (pageBadge) pageBadge.innerText = `(${count})`;

    } catch (e) {
        console.warn("Cart count update failed", e);
        // Fail hone par badge chupa do
        badge.style.display = 'none';
    }
};