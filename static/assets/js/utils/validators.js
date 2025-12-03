// static/assets/js/utils/validators.js

const Validators = {
    /**
     * Validates Indian Mobile Number (+91 optional, 10 digits required)
     */
    isValidPhone: (phone) => {
        const phoneRegex = /^(?:\+91|91)?[6-9]\d{9}$/;
        return phoneRegex.test(phone);
    },

    /**
     * Validates 6-digit OTP
     */
    isValidOTP: (otp) => {
        const otpRegex = /^\d{6}$/;
        return otpRegex.test(otp);
    },

    /**
     * Validates Indian Pincode (6 digits)
     */
    isValidPincode: (pincode) => {
        const pinRegex = /^[1-9][0-9]{5}$/;
        return pinRegex.test(pincode);
    },

    /**
     * Checks if string is not empty
     */
    isRequired: (value) => {
        return value && value.trim().length > 0;
    },

    /**
     * Basic Email Validation
     */
    isValidEmail: (email) => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }
};

// Error Display Helper
function showInputError(inputElement, message) {
    // Remove existing error if any
    const existingError = inputElement.parentElement.querySelector('.error-msg');
    if (existingError) existingError.remove();

    // Add red border
    inputElement.style.borderColor = '#e53935';

    // Create error text
    const error = document.createElement('small');
    error.className = 'error-msg';
    error.style.color = '#e53935';
    error.style.fontSize = '0.8rem';
    error.style.marginTop = '4px';
    error.innerText = message;

    inputElement.parentElement.appendChild(error);
}

function clearInputError(inputElement) {
    inputElement.style.borderColor = '#e0e0e0';
    const existingError = inputElement.parentElement.querySelector('.error-msg');
    if (existingError) existingError.remove();
}