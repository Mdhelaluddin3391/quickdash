/* static/assets/js/utils/base.js */

document.addEventListener('DOMContentLoaded', () => {
    initLocationWidget();
    loadNavbarCategories(); 
    if (window.updateGlobalCartCount) window.updateGlobalCartCount();
});


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
            if (currentSlug === cat.slug) {
                link.classList.add('active');
            }

            nav.appendChild(link);
        });

    } catch (error) {
        console.error("Navbar Categories Error:", error);
    }
}

async function initLocationWidget() {
    const locText = document.getElementById('header-location');
    if (!locText) return;

    // [FIX] Sahi key 'access_token' use karein
    const token = localStorage.getItem('access_token');

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
            console.warn("Address fetch failed (User might be logged out)", e);
            // Agar fail ho, toh guest user wala logic chalne do
        }
    }

    // Guest User Logic (Browser GPS)
    if (navigator.geolocation) {
        locText.innerText = "Locating...";
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const { latitude, longitude } = pos.coords;
                checkServiceabilityAndRedirect(latitude, longitude, "Current Location");
            },
            (err) => {
                locText.innerHTML = `<span style="cursor:pointer" onclick="window.location.href='/location_denied.html'">Enable Location</span>`;
            }
        );
    } else {
        locText.innerText = "Location Unavailable";
    }
}

async function checkServiceabilityAndRedirect(lat, lng, cityName) {
    const locText = document.getElementById('header-location');
    
    try {
        const response = await apiCall('/delivery/estimate/', 'POST', { lat, lng }, false);

        const currentPath = window.location.pathname;
        const safePages = [
            '/addresses.html', 
            '/profile.html', 
            '/auth.html', 
            '/service-unavailable.html'
        ];

        if (!response.serviceable) {
            if (!safePages.includes(currentPath)) {
                window.location.href = '/service-unavailable.html';
                return; 
            }
            if(locText) {
                locText.innerHTML = `<span style="color:red; font-weight:bold;">Not Serviceable</span> • ${cityName}`;
            }
        } else {
            if (currentPath === '/service-unavailable.html') {
                window.location.href = '/';
                return;
            }
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