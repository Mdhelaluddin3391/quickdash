// assets/js/utils/api.js

const CONFIG = window.APP_CONFIG || { API_BASE: "/api/v1", LOGIN_URL: "/auth.html" };

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

async function apiCall(endpoint, method = 'GET', body = null, requireAuth = false) {
    const headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken') // Important for Django
    };

    if (requireAuth) {
        const token = localStorage.getItem('accessToken');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        } else {
            redirectToLogin();
            throw new Error("Authentication required");
        }
    }

    const config = { method, headers };
    if (body) config.body = JSON.stringify(body);

    try {
        const response = await fetch(`${CONFIG.API_BASE}${endpoint}`, config);

        if (response.status === 401 && requireAuth) {
            console.warn("Session expired. Redirecting...");
            localStorage.removeItem('accessToken');
            redirectToLogin();
            throw new Error("Session expired");
        }

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || data.error || "Request failed");
        }
        return data;
    } catch (error) {
        console.error("API Call Failed:", error);
        throw error;
    }
}

function redirectToLogin() {
    const currentPath = window.location.pathname + window.location.search;
    window.location.href = `${CONFIG.LOGIN_URL}?next=${encodeURIComponent(currentPath)}`;
}

function isLoggedIn() {
    return !!localStorage.getItem('accessToken');
}

function logout() {
    localStorage.clear();
    window.location.href = CONFIG.LOGIN_URL;
}

// Auto-update cart count on load
document.addEventListener('DOMContentLoaded', async () => {
    const cartBadges = document.querySelectorAll('.cart-count');
    if (cartBadges.length > 0 && isLoggedIn()) {
        try {
            const cart = await apiCall('/orders/cart/', 'GET', null, true);
            const count = cart.items.reduce((acc, item) => acc + item.quantity, 0);
            cartBadges.forEach(el => {
                el.innerText = count;
                el.style.display = count > 0 ? 'inline-flex' : 'none';
            });
        } catch (e) { /* silent fail */ }
    }
});