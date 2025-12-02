// static/assets/js/utils/api.js

const CONFIG = window.APP_CONFIG || { API_BASE: "/api/v1" };

// --- Toast Notification Helper ---
function showToast(message, type = 'success') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}" 
           style="color: ${type === 'success' ? 'var(--primary)' : type === 'error' ? 'var(--danger)' : 'var(--secondary)'}"></i>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// --- Cookie Helper (CSRF) ---
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

// --- Token Refresh Logic ---
async function refreshToken() {
    const refresh = localStorage.getItem('refreshToken');
    if (!refresh) return false;

    try {
        const response = await fetch(`${CONFIG.API_BASE}/auth/token/refresh/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh })
        });

        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('accessToken', data.access);
            if (data.refresh) localStorage.setItem('refreshToken', data.refresh);
            return true;
        }
    } catch (e) { console.error("Token refresh failed", e); }
    return false;
}

// --- Main API Caller ---
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

        // Handle 401 Unauthorized (Token Expired)
        if (response.status === 401 && requireAuth) {
            console.log("401 detected, attempting refresh...");
            const refreshed = await refreshToken();
            if (refreshed) {
                // Retry with new token
                token = localStorage.getItem('accessToken');
                headers['Authorization'] = `Bearer ${token}`;
                config.headers = headers;
                response = await fetch(`${CONFIG.API_BASE}${endpoint}`, config);
            } else {
                logout(); // Session expired
                throw new Error("Session expired. Please login again.");
            }
        }

        if (response.status === 204) return null;

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

// --- Auth Helpers ---
function isLoggedIn() {
    return !!localStorage.getItem('accessToken');
}

function logout() {
    localStorage.clear();
    window.location.href = CONFIG.LOGIN_URL || '/auth.html';
}

function getUser() {
    try {
        return JSON.parse(localStorage.getItem('user')) || null;
    } catch { return null; }
}

// --- Global Cart Count ---
window.updateGlobalCartCount = async function() {
    if (!isLoggedIn()) return;
    const badge = document.querySelector('.cart-count');
    if (!badge) return;

    try {
        const cart = await apiCall('/orders/cart/', 'GET', null, true);
        const count = cart.items ? cart.items.reduce((acc, item) => acc + item.quantity, 0) : 0;
        badge.innerText = count;
        badge.style.display = count > 0 ? 'flex' : 'none';
    } catch (e) {
        console.log("Cart fetch silent fail");
    }
};

document.addEventListener('DOMContentLoaded', () => {
    window.updateGlobalCartCount();
});