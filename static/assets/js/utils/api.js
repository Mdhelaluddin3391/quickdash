// assets/js/utils/api.js

const CONFIG = window.APP_CONFIG || { 
    API_BASE: "/api/v1", 
    LOGIN_URL: "/auth.html" 
};

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

async function refreshToken() {
    const refresh = localStorage.getItem('refreshToken');
    if(!refresh) return false;

    try {
        const response = await fetch(`${CONFIG.API_BASE}/auth/token/refresh/`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({refresh: refresh})
        });
        
        if(response.ok) {
            const data = await response.json();
            localStorage.setItem('accessToken', data.access);
            if(data.refresh) localStorage.setItem('refreshToken', data.refresh);
            return true;
        }
    } catch(e) { console.error("Refresh failed", e); }
    
    return false;
}

async function apiCall(endpoint, method = 'GET', body = null, requireAuth = false) {
    let token = localStorage.getItem('accessToken');
    
    const headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
    };

    if (requireAuth && token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const config = { method, headers };
    if (body) config.body = JSON.stringify(body);

    try {
        let response = await fetch(`${CONFIG.API_BASE}${endpoint}`, config);

        // 401: Token Expired? Try Refresh
        if (response.status === 401 && requireAuth) {
            console.log("Token expired, attempting refresh...");
            const refreshed = await refreshToken();
            if(refreshed) {
                // Retry original request
                token = localStorage.getItem('accessToken');
                headers['Authorization'] = `Bearer ${token}`;
                config.headers = headers;
                response = await fetch(`${CONFIG.API_BASE}${endpoint}`, config);
            } else {
                console.warn("Session expired completely.");
                logout();
                throw new Error("Session expired");
            }
        }

        if (response.status === 204) return null;

        const data = await response.json();
        
        if (!response.ok) {
            const errorMsg = data.detail || data.error || "Request failed";
            throw new Error(errorMsg);
        }
        
        return data;

    } catch (error) {
        console.error(`API Error:`, error);
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

window.updateGlobalCartCount = async function() {
    if (!isLoggedIn()) return;
    const cartBadges = document.querySelectorAll('.cart-count');
    if (cartBadges.length > 0) {
        try {
            const cart = await apiCall('/orders/cart/', 'GET', null, true);
            const count = cart.items ? cart.items.reduce((acc, item) => acc + item.quantity, 0) : 0;
            cartBadges.forEach(el => {
                el.innerText = count;
                el.style.display = count > 0 ? 'inline-flex' : 'none';
            });
        } catch (e) { console.log("Cart sync silent fail"); }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    window.updateGlobalCartCount();
});