// static/assets/js/utils/api.js

const API_CONFIG = {
    BASE_URL: '/api/v1',
    LOGIN_URL: '/auth.html',
};

/**
 * Generic API Call Function
 * Handles Auth Tokens, Errors, and JSON parsing automatically.
 */
let isRefreshing = false;
let refreshPromise = null;

/**
 * Generic API Call Function
 * Handles Auth Tokens, Errors, and JSON parsing automatically.
 */
async function apiCall(endpoint, method = 'GET', body = null, requireAuth = true) {
    const executeFetch = async () => {
        let token = localStorage.getItem('accessToken');
        const headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        };
        if (requireAuth && token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const config = { method, headers };
        if (body) {
            config.body = JSON.stringify(body);
        }
        return fetch(`${API_CONFIG.BASE_URL}${endpoint}`, config);
    };

    try {
        let response = await executeFetch();

        if (response.status === 401 && requireAuth) {
            console.warn("Access Token Expired. Handling Refresh...");

            if (!isRefreshing) {
                // If not already refreshing, start the refresh process
                isRefreshing = true;
                refreshPromise = refreshToken().finally(() => {
                    isRefreshing = false;
                    refreshPromise = null; // Clear the promise
                });
            }

            // Wait for the ongoing refresh to complete
            const refreshSuccess = await refreshPromise;

            if (refreshSuccess) {
                // Retry original request with the new token
                response = await executeFetch();
            } else {
                // Refresh failed, logout user
                logout();
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

/**
 * Refreshes the JWT Access Token using the Refresh Token
 */
async function refreshToken() {
    const refresh = localStorage.getItem('refreshToken');
    if (!refresh) {
        console.error("No refresh token available.");
        return false;
    }

    try {
        const response = await fetch(`${API_CONFIG.BASE_URL}/auth/token/refresh/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh })
        });

        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('accessToken', data.access);
            if (data.refresh) localStorage.setItem('refreshToken', data.refresh);
            console.log("Token successfully refreshed.");
            return true;
        } else {
            console.error("Token refresh API call failed with status:", response.status);
            return false;
        }
    } catch (e) {
        console.error("An error occurred during token refresh:", e);
        return false;
    }
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