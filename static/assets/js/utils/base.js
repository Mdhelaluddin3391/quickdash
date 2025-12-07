document.addEventListener('DOMContentLoaded', () => {
    initLocationWidget();
    loadNavbarCategories(); // Navbar load karne ke liye call
    if (window.updateGlobalCartCount) window.updateGlobalCartCount();
});


async function loadNavbarCategories() {
    const nav = document.getElementById('dynamic-navbar');
    if (!nav) return;

    try {
        // API se saari categories mangwao (Limit 100 taaki saari parents aa jayein)
        const response = await apiCall('/catalog/categories/?page_size=100', 'GET', null, false);
        const allCategories = response.results || response;

        // Sirf Parent Categories filter karein (jinka koi parent nahi hai)
        const parentCategories = allCategories.filter(c => !c.parent);

        // Har category ke liye link banao aur append karo
        parentCategories.forEach(cat => {
            const link = document.createElement('a');

            // Search page par slug ke saath bhejo
            link.href = `/search_results.html?slug=${cat.slug}`;
            link.className = 'nav-item';
            link.innerText = cat.name;

            // Agar user abhi is category ke page par hai, toh 'active' class lagao
            const currentSlug = new URLSearchParams(window.location.search).get('slug');
            if (currentSlug === cat.slug) {
                link.classList.add('active');
            }

            nav.appendChild(link);
        });

    } catch (error) {
        console.error("Navbar Categories Error:", error);
        // Error aaye toh kuch mat dikhao ya retry button de sakte ho
    }
}

async function initLocationWidget() {
    const locText = document.getElementById('header-location');
    if (!locText) return;

    const token = localStorage.getItem('accessToken');

    if (token) {
        try {
            const response = await apiCall('/auth/customer/addresses/');
            
            // --- FIX: Handle Pagination ---
            const addresses = response.results || response;

            const defaultAddr = addresses.find(a => a.is_default) || addresses[0];

            if (defaultAddr && defaultAddr.latitude) {
                updateNavbarWithETA(defaultAddr.latitude, defaultAddr.longitude, defaultAddr.city);
                return;
            }
        } catch (e) {
            console.warn("Could not fetch user address", e);
        }
    }

    if (navigator.geolocation) {
        locText.innerText = "Locating...";
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const { latitude, longitude } = pos.coords;
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



// --- Cart Count Global Helper ---
window.updateGlobalCartCount = async function () {
    const badge = document.getElementById('nav-cart-count');
    if (!badge) return;

    // Login check
    if (!localStorage.getItem('accessToken')) {
        badge.innerText = '0';
        badge.style.display = 'none';
        return;
    }

    try {
        const cart = await apiCall('/orders/cart/');
        const count = cart.items ? cart.items.length : 0;

        badge.innerText = count;
        badge.style.display = count > 0 ? 'flex' : 'none';

        // Cart page par bhi update karein agar element maujood hai
        const pageBadge = document.getElementById('cart-count-badge');
        if (pageBadge) pageBadge.innerText = `(${count})`;

    } catch (e) {
        console.warn("Cart count update failed");
    }
};



