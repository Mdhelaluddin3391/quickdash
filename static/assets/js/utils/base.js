/* static/assets/js/utils/base.js */

document.addEventListener('DOMContentLoaded', () => {
    initLocationWidget();
    loadNavbarCategories(); 
    checkAndShowLocationPopup(); // Soft ask popup
    bindNavbarLocationClick();   // New listener for Navbar click
    if (window.updateGlobalCartCount) window.updateGlobalCartCount();
});

// --- NAVBAR CLICK BINDING ---
function bindNavbarLocationClick() {
    const navLocBtn = document.getElementById('navbar-location-box');
    if (navLocBtn) {
        navLocBtn.addEventListener('click', (e) => {
            e.preventDefault();
            // Open the new Map Modal
            if (window.LocationPicker) {
                LocationPicker.open();
            } else {
                console.error("LocationPicker module not loaded");
            }
        });
    }
}

// --- POPUP LOGIC ---
function checkAndShowLocationPopup() {
    const dismissed = sessionStorage.getItem('location_popup_dismissed');
    const hasLocation = localStorage.getItem('user_lat') && localStorage.getItem('user_lng'); 
    
    // If no location & not dismissed, show bottom sheet
    if (!dismissed && !hasLocation) {
        setTimeout(() => {
            const sheet = document.getElementById('location-bottom-sheet');
            const overlay = document.getElementById('location-popup-overlay');
            if (sheet && overlay) {
                sheet.style.bottom = '0';
                overlay.style.display = 'block';
            }
        }, 1500); 
    }
}

window.closeLocationPopup = function() {
    const sheet = document.getElementById('location-bottom-sheet');
    const overlay = document.getElementById('location-popup-overlay');
    
    if (sheet) sheet.style.bottom = '-100%';
    if (overlay) overlay.style.display = 'none';
    
    sessionStorage.setItem('location_popup_dismissed', 'true');
};

// --- UPDATED: Connects Bottom Sheet "Use Current Location" to New Picker ---
window.requestUserLocation = function() {
    // 1. Close the soft popup
    closeLocationPopup(); 
    
    // 2. Open the Main Map Modal
    if (window.LocationPicker) {
        LocationPicker.open();       // Show Modal
        LocationPicker.triggerGPS(); // Auto-start GPS logic inside the map
    } else {
        alert("Location System loading... please try again.");
    }
};

// --- EXISTING FUNCTIONS ---

async function loadNavbarCategories() {
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

    // 1. Check if we have a temporary session location (from LocationPicker)
    const savedAddress = localStorage.getItem('user_address_text');
    if (savedAddress) {
        locText.innerText = savedAddress;
        return;
    }

    // 2. Fallback: Check Backend Profile if logged in
    const token = localStorage.getItem('access_token');
    if (token) {
        try {
            const response = await apiCall('/auth/customer/addresses/');
            const addresses = response.results || response;
            const defaultAddr = addresses.find(a => a.is_default) || addresses[0];

            if (defaultAddr && defaultAddr.city) {
                locText.innerText = `${defaultAddr.address_text || defaultAddr.city}`;
                // Cache it locally to avoid API call next reload
                localStorage.setItem('user_address_text', defaultAddr.city);
            }
        } catch (e) {
            console.warn("Address fetch failed", e);
        }
    }
}

// --- Cart Count Global Helper ---
window.updateGlobalCartCount = async function () {
    const badge = document.getElementById('nav-cart-count');
    if (!badge) return;

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
    } catch (e) {
        badge.style.display = 'none';
    }
};