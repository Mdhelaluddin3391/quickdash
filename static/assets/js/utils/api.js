/* static/assets/js/utils/api.js */
const API_BASE = '/api/v1'; 

// Helper to get full URL if needed
const getFullApiUrl = (endpoint) => `${window.location.origin}${API_BASE}${endpoint}`;

async function apiCall(endpoint, method = 'GET', body = null, auth = true) {
    const headers = { 'Content-Type': 'application/json' };
    
    if (auth) {
        const token = localStorage.getItem('access_token');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
    }

    const config = { method, headers };
    if (body) {
        config.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, config);
        
        // Handle 401 Unauthorized (Session Expired)
        if (response.status === 401 && auth) {
            console.warn("Session expired. Redirecting to login...");
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('user');
            window.location.href = '/auth.html';
            throw new Error("Unauthorized - Session Expired");
        }

        const data = await response.json();
        
        if (!response.ok) {
            // Extract error message from DRF structure
            const errorMessage = data.detail || data.error || (data.non_field_errors ? data.non_field_errors[0] : 'Something went wrong');
            throw new Error(errorMessage);
        }
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// Expose to global window scope
window.apiCall = apiCall;
window.getFullApiUrl = getFullApiUrl;