/* static/assets/js/utils/api.js */

const API_BASE = '/api/v1'; 

const getFullApiUrl = (endpoint) => {
    return `${window.location.origin}${API_BASE}${endpoint}`;
};

async function apiCall(endpoint, method = 'GET', body = null, auth = true) {
    const headers = {
        'Content-Type': 'application/json',
    };

    if (auth) {
        // [Correction] Token key name standardized to 'access_token'
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
        
        // --- FIX START: Handle 401 gracefully ---
        if (response.status === 401 && auth) {
            console.warn("Session expired. Clearing token...");
            
            // Token delete kar do taaki agli baar ye error na aaye
            localStorage.removeItem('access_token');
            localStorage.removeItem('accessToken'); // Safety ke liye dono hata rahe hain

            // [IMPORTANT] Redirect mat karo! Sirf error throw karo.
            // Isse homepage band nahi hoga, bas user logout ho jayega.
            // window.location.href = '/auth.html'; // <-- YE LINE COMMENT/REMOVE KAR DI HAI
            
            throw new Error("Unauthorized - Session Expired");
        }
        // --- FIX END ---

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

window.apiCall = apiCall;
window.getFullApiUrl = getFullApiUrl;