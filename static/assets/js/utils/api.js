/**
 * QuickDash API Utility
 * Handles authentication, base URLs, and error parsing.
 */

// Establish API_BASE with Safe Fallbacks:
// 1. window.API_BASE (Explicit global from base.html)
// 2. window.APP_CONFIG.API_BASE (Namespaced config)
// 3. '/api/v1' (Safe default for same-origin calls)
const API_BASE = (typeof window.API_BASE !== 'undefined') 
    ? window.API_BASE 
    : (window.APP_CONFIG && window.APP_CONFIG.API_BASE) 
        ? window.APP_CONFIG.API_BASE 
        : '/api/v1';

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
        // Handle Absolute vs Relative URLs
        let url = endpoint;
        if (!endpoint.startsWith('http://') && !endpoint.startsWith('https://')) {
            // Ensure endpoint has leading slash if missing to avoid concatenation errors
            const safeEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
            
            // API_BASE is now guaranteed to be defined by the const above
            url = `${API_BASE}${safeEndpoint}`;
        }

        const response = await fetch(url, config);
        
        // Handle 401 Unauthorized (Session Expired)
        if (response.status === 401 && auth) {
            console.warn("Session expired. Redirecting to login...");
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('user');
            window.location.href = '/auth.html';
            throw new Error("Unauthorized - Session Expired");
        }

        // Safety: Check if response is JSON
        const contentType = response.headers.get("content-type");
        if (contentType && !contentType.includes("application/json")) {
            if (!response.ok) throw new Error(`API Error: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        
        // Handle Backend-Directed Redirects
        if (data.redirect_url) {
            window.location.href = data.redirect_url;
            return;
        }

        if (!response.ok) {
            const errorMessage = data.detail || data.error || (data.non_field_errors ? data.non_field_errors[0] : 'Something went wrong');
            throw new Error(errorMessage);
        }
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}