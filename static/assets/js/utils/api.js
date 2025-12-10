/* static/assets/js/utils/api.js */
const API_BASE = '/api/v1'; 
const getFullApiUrl = (endpoint) => `${window.location.origin}${API_BASE}${endpoint}`;

async function apiCall(endpoint, method = 'GET', body = null, auth = true) {
    const headers = { 'Content-Type': 'application/json' };
    if (auth) {
        const token = localStorage.getItem('access_token');
        if (token) headers['Authorization'] = `Bearer ${token}`;
    }
    const config = { method, headers };
    if (body) config.body = JSON.stringify(body);

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, config);
        if (response.status === 401 && auth) {
            console.warn("Session expired.");
            localStorage.removeItem('access_token');
            throw new Error("Unauthorized - Session Expired");
        }
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || data.error || 'Something went wrong');
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}
window.apiCall = apiCall;
window.getFullApiUrl = getFullApiUrl;