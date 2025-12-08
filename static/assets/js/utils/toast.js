// static/assets/js/utils/toast.js
/**
 * Simple Toast Notification System
 * Usage: showToast("Message", "success") | showToast("Error", "error") | showToast("Info", "info")
 */

function showToast(message, type = 'info', duration = 3000) {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    // Set icon based on type
    let icon = '🔔';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';
    if (type === 'warning') icon = '⚠️';
    if (type === 'info') icon = 'ℹ️';
    
    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">✕</button>
    `;
    
    toastContainer.appendChild(toast);
    
    // Auto remove toast after duration
    setTimeout(() => {
        if (toast.parentElement) {
            toast.classList.add('toast-exit');
            setTimeout(() => toast.remove(), 300);
        }
    }, duration);
}

// Shortcuts
function showSuccess(message, duration) { showToast(message, 'success', duration); }
function showError(message, duration) { showToast(message, 'error', duration); }
function showWarning(message, duration) { showToast(message, 'warning', duration); }
function showInfo(message, duration) { showToast(message, 'info', duration); }
