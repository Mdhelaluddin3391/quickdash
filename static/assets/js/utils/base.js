/* static/assets/js/utils/base.js */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Global Widgets
    initGlobalLocationWidget();
    loadNavbarCategories(); 
    bindNavbarLocationClick();
    
    // 2. Global Cart Count (Safe execution)
    if (window.updateGlobalCartCount) {
        window.updateGlobalCartCount();
    }

    // NOTE: Location Popup logic has been moved entirely to LocationManager.js
    // to prevent race conditions and duplicate logic.
});

// --- NAVBAR & INTERACTION ---

function bindNavbarLocationClick() {
    const navLocBtn = document.getElementById('navbar-location-box');
    if (navLocBtn) {
        navLocBtn.addEventListener('click', (e) => {
            e.preventDefault();
            
            // Standardized call to open the Map Modal
            if (window.LocationPicker) {
                LocationPicker.open();
            } else {
                console.error("LocationPicker module not loaded");
                // Fallback: If LocationManager is present, maybe trigger a check?
                if (window.LocationManager) window.LocationManager.requestUserLocation();
            }
        });
    }
}

/**
 * Global Handler for "Use Current Location" button (in Bottom Sheet).
 * This bridges the "Soft Popup" to the "Hard Map Modal".
 */
window.requestUserLocation = function() {
    // 1. Close the soft popup (Delegated to LocationManager)
    if (window.LocationManager) {
        window.LocationManager.close();
    } else {
        // Fallback for legacy DOM elements
        const sheet = document.getElementById('location-bottom-sheet');
        const overlay = document.getElementById('location-popup-overlay');
        if (sheet) sheet.style.bottom = '-100%';
        if (overlay) overlay.style.display = 'none';
    }
    
    // 2. Open the Main Map Modal with GPS Auto-Start
    if (window.LocationPicker) {
        LocationPicker.open();       // Show Modal
        LocationPicker.triggerGPS(); // Auto-start GPS logic inside the map
    } else {
        // If LocationPicker fails, fallback to Manager's blind check
        if(window.LocationManager) {
            window.LocationManager.requestUserLocation(); 
        } else {
            alert("Location System loading... please try again.");
        }
    }
};

// --- DATA FETCHING ---

async function loadNavbarCategories() {
    const nav = document.getElementById('dynamic-navbar');
    if (!nav) return;
    
    try {
        // Standardized API Call
        const response = await apiCall('/catalog/categories/?page_size=100', 'GET', null, false);
        
        // Handle pagination structure (results vs list)
        const allCategories = response.results || response;
        const parentCategories = allCategories.filter(c => !c.parent);
        
        // Clear existing (if any placeholders existed)
        nav.innerHTML = '';

        parentCategories.forEach(cat => {
            const link = document.createElement('a');
            
            // Use Centralized URL Config if available, else fallback
            const baseUrl = (window.APP_CONFIG && window.APP_CONFIG.URLS) 
                ? window.APP_CONFIG.URLS.SEARCH 
                : '/search_results.html';
                
            link.href = `${baseUrl}?slug=${cat.slug}`;
            link.className = 'nav-item';
            link.innerText = cat.name;
            
            // Highlight active category
            const currentSlug = new URLSearchParams(window.location.search).get('slug');
            if (currentSlug === cat.slug) link.classList.add('active');
            
            nav.appendChild(link);
        });
    } catch (error) { 
        console.warn("[Navbar] Failed to load categories", error); 
    }
}

/**
 * Updates the Header Location Text.
 * Priority:
 * 1. Session Storage (Immediate visual feedback)
 * 2. APP_CONFIG (Server-side injected)
 * 3. API Profile Fetch (Slowest, but most accurate)
 */
async function initGlobalLocationWidget() {
    const locText = document.getElementById('header-location');
    if (!locText) return;

    // 1. Check if we have a temporary session location (from LocationPicker)
    const savedAddress = localStorage.getItem('user_address_text');
    if (savedAddress) {
        locText.innerText = savedAddress;
        return;
    }

    // 2. Check Backend Profile if logged in
    // Using APP_CONFIG.IS_LOGGED_IN is safer than checking token string manually
    if (window.APP_CONFIG && window.APP_CONFIG.IS_LOGGED_IN) {
        try {
            const response = await apiCall('/auth/customer/addresses/');
            const addresses = response.results || response;
            const defaultAddr = addresses.find(a => a.is_default) || addresses[0];

            if (defaultAddr && defaultAddr.city) {
                const displayText = defaultAddr.address_text || defaultAddr.city;
                locText.innerText = displayText;
                // Cache it locally to avoid API call next reload
                localStorage.setItem('user_address_text', displayText);
            }
        } catch (e) {
            console.warn("[LocationWidget] Address fetch failed", e);
        }
    }
}

// --- GLOBAL UTILS ---

/**
 * Updates the Cart Badge Count.
 * Can be called from anywhere (Add to Cart, Checkout, etc.)
 */
window.updateGlobalCartCount = async function () {
    const badge = document.getElementById('nav-cart-count');
    if (!badge) return;

    // Use Centralized Config
    if (!window.APP_CONFIG || !window.APP_CONFIG.IS_LOGGED_IN) {
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
        console.warn("[Cart] Count update failed", e);
        badge.style.display = 'none';
    }
};