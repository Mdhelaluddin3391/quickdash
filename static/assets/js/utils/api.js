/* static/assets/js/utils/api.js */

const API_BASE = '/api/v1'; // Use relative path to avoid CORS and hardcoding

// Helper to get full URL if needed (e.g. for external links)
const getFullApiUrl = (endpoint) => {
    return `${window.location.origin}${API_BASE}${endpoint}`;
};

async function apiCall(endpoint, method = 'GET', body = null, auth = true) {
    const headers = {
        'Content-Type': 'application/json',
    };

    if (auth) {
        const token = localStorage.getItem('access_token');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
    }

    const config = {
        method,
        headers,
    };

    if (body) {
        config.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, config);
        
        // Handle 401 Unauthorized globally
        if (response.status === 401 && auth) {
            console.warn("Unauthorized access. Redirecting to login...");
            window.location.href = '/auth.html';
            return;
        }

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || data.error || 'Something went wrong');
        }
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// Export functions if using modules, otherwise they are global
window.apiCall = apiCall;
window.getFullApiUrl = getFullApiUrl;