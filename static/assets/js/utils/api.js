// static/assets/js/utils/api.js

const API_CONFIG = {
    BASE_URL: '/api/v1',
    LOGIN_URL: '/auth.html',
};

/**
 * Generic API Call Function
 * Handles Auth Tokens, Errors, and JSON parsing automatically.
 */
async function apiCall(endpoint, method = 'GET', body = null, requireAuth = true) {
    let token = localStorage.getItem('accessToken');
    
    const headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken') // Django CSRF protection
    };

    if (requireAuth && token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const config = {
        method: method,
        headers: headers,
    };

    if (body) {
        config.body = JSON.stringify(body);
    }

    try {
        let response = await fetch(`${API_CONFIG.BASE_URL}${endpoint}`, config);

        // --- Token Expiry Handling (401 Unauthorized) ---
        if (response.status === 401 && requireAuth) {
            console.warn("Access Token Expired. Attempting Refresh...");
            const refreshSuccess = await refreshToken();
            
            if (refreshSuccess) {
                // Retry original request with new token
                token = localStorage.getItem('accessToken');
                headers['Authorization'] = `Bearer ${token}`;
                config.headers = headers;
                response = await fetch(`${API_CONFIG.BASE_URL}${endpoint}`, config);
            } else {
                // Refresh failed, logout user
                logout();
                throw new Error("Session expired. Please login again.");
            }
        }

        // Handle empty responses (like 204 No Content)
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

/**
 * Refreshes the JWT Access Token using the Refresh Token
 */
async function refreshToken() {
    const refresh = localStorage.getItem('refreshToken');
    if (!refresh) return false;

    try {
        const response = await fetch(`${API_CONFIG.BASE_URL}/auth/token/refresh/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh: refresh })
        });

        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('accessToken', data.access);
            // Rotate refresh token if backend sends a new one
            if (data.refresh) localStorage.setItem('refreshToken', data.refresh);
            return true;
        }
    } catch (e) {
        console.error("Token refresh failed:", e);
    }
    return false;
}

// --- Helper: Get CSRF Cookie ---
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

// --- Auth Helpers ---
function logout() {
    localStorage.clear();
    window.location.href = API_CONFIG.LOGIN_URL;
}

function isLoggedIn() {
    return !!localStorage.getItem('accessToken');
}