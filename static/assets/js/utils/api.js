// assets/js/utils/api.js

const CONFIG = window.APP_CONFIG || { 
    API_BASE: "/api/v1", 
    LOGIN_URL: "/auth.html" 
};

/**
 * Gets Django CSRF token from cookies
 */
function getCookie(name) {
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

/**
 * Main API Wrapper
 */
async function apiCall(endpoint, method = 'GET', body = null, requireAuth = false) {
    const headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
    };

    if (requireAuth) {
        const token = localStorage.getItem('accessToken');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        } else {
            console.warn("Auth required but no token found.");
            redirectToLogin();
            throw new Error("Authentication required");
        }
    }

    const config = { method, headers };
    if (body) config.body = JSON.stringify(body);

    try {
        const response = await fetch(`${CONFIG.API_BASE}${endpoint}`, config);

        // 1. Handle 401 Unauthorized (Token Expired/Invalid)
        if (response.status === 401 && requireAuth) {
            console.warn("Session expired (401). clearing token and redirecting.");
            localStorage.removeItem('accessToken');
            localStorage.removeItem('user');
            redirectToLogin();
            throw new Error("Session expired");
        }

        // 2. Handle 204 No Content
        if (response.status === 204) {
            return null;
        }

        const data = await response.json();
        
        // 3. Handle Logical Errors (4xx, 5xx)
        if (!response.ok) {
            const errorMsg = data.detail || data.error || JSON.stringify(data) || "Request failed";
            throw new Error(errorMsg);
        }
        
        return data;

    } catch (error) {
        console.error(`API Error [${method} ${endpoint}]:`, error);
        throw error;
    }
}

function redirectToLogin() {
    // Preserve current location for redirect back
    if (!window.location.pathname.includes('auth.html')) {
        const currentPath = window.location.pathname + window.location.search;
        window.location.href = `${CONFIG.LOGIN_URL}?next=${encodeURIComponent(currentPath)}`;
    }
}

function isLoggedIn() {
    return !!localStorage.getItem('accessToken');
}

function logout() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('user');
    window.location.href = CONFIG.LOGIN_URL;
}

// Global Cart Count Updater
// Can be called by any page after adding to cart
window.updateGlobalCartCount = async function() {
    const cartBadges = document.querySelectorAll('.cart-count');
    if (cartBadges.length > 0 && isLoggedIn()) {
        try {
            const cart = await apiCall('/orders/cart/', 'GET', null, true);
            // Sum quantity of all items
            const count = cart.items.reduce((acc, item) => acc + item.quantity, 0);
            
            cartBadges.forEach(el => {
                el.innerText = count;
                el.style.display = count > 0 ? 'inline-flex' : 'none';
            });
        } catch (e) { 
            console.log("Cart fetch failed (likely empty)", e); 
        }
    }
};

// Auto-init on load
document.addEventListener('DOMContentLoaded', () => {
    window.updateGlobalCartCount();
});