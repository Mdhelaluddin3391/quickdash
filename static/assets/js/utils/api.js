// assets/js/utils/api.js

// Use the config injected from HTML, or fallback for safety
const CONFIG = window.APP_CONFIG || { API_BASE: "/api/v1", LOGIN_URL: "auth.html" };

async function apiCall(endpoint, method = 'GET', body = null, requireAuth = false) {
    const headers = {
        'Content-Type': 'application/json'
    };

    if (requireAuth) {
        const token = localStorage.getItem('accessToken');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        } else {
            // Smart Redirect using dynamic URL
            if (window.location.pathname.indexOf(CONFIG.LOGIN_URL) === -1) {
                const currentPath = window.location.pathname + window.location.search;
                window.location.href = `${CONFIG.LOGIN_URL}?next=${encodeURIComponent(currentPath)}`;
            }
            throw new Error("Authentication required");
        }
    }

    const config = { method, headers };
    if (body) config.body = JSON.stringify(body);

    try {
        const response = await fetch(`${CONFIG.API_BASE}${endpoint}`, config);

        if (response.status === 401 && requireAuth) {
            logout();
            throw new Error("Session expired");
        }

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || data.error || "Something went wrong");
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
    window.location.href = CONFIG.LOGIN_URL;
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