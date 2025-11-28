// assets/js/utils/api.js

// [PRODUCTION FIX] Use relative path. Nginx handles the proxy to backend.
const API_BASE = "/api/v1"; 

async function apiCall(endpoint, method = 'GET', body = null, requireAuth = false) {
    const headers = {
        'Content-Type': 'application/json'
    };

    if (requireAuth) {
        const token = localStorage.getItem('accessToken');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        } else {
            // [PRODUCTION FIX] Smart Redirect: Save current page to return after login
            if (window.location.pathname.indexOf('auth.html') === -1) {
                const currentPath = window.location.pathname + window.location.search;
                window.location.href = `auth.html?next=${encodeURIComponent(currentPath)}`;
            }
            throw new Error("Authentication required");
        }
    }

    const config = {
        method: method,
        headers: headers
    };

    if (body) {
        config.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, config);

        // Token expire hone par logout
        if (response.status === 401 && requireAuth) {
            logout();
            throw new Error("Session expired");
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || data.error || JSON.stringify(data) || "Something went wrong");
        }
        return data;
    } catch (error) {
        console.error("API Error:", error);
        throw error;
    }
}

function isLoggedIn() {
    return !!localStorage.getItem('accessToken');
}

function logout() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('user');
    window.location.href = 'auth.html';
}

// Global Cart Count Update
async function updateGlobalCartCount() {
    const cartCountEls = document.querySelectorAll('.cart-count');
    if (cartCountEls.length === 0 || !isLoggedIn()) return;

    try {
        const cart = await apiCall('/orders/cart/', 'GET', null, true);
        // Total Quantity Count
        const count = cart.items.reduce((acc, item) => acc + item.quantity, 0);
        
        cartCountEls.forEach(el => {
            el.innerText = count;
            el.style.display = count > 0 ? 'flex' : 'none';
        });
    } catch (e) {
        console.log("Cart fetch failed (silent)", e);
    }
}

document.addEventListener('DOMContentLoaded', updateGlobalCartCount);