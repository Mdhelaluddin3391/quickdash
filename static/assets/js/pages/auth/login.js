// static/assets/js/pages/auth/login.js

document.addEventListener('DOMContentLoaded', () => {
    const phoneForm = document.getElementById('phone-form');
    const otpForm = document.getElementById('otp-form');
    const phoneInput = document.getElementById('phone');
    const otpInputs = document.querySelectorAll('.otp-field');
    
    let userPhone = '';

    // === OTP Input Logic (Auto-focus & Validation) ===
    if (otpInputs.length > 0) {
        otpInputs.forEach((input, index) => {
            // 1. Auto-focus next on input
            input.addEventListener('input', (e) => {
                if (input.value.length === 1 && index < otpInputs.length - 1) {
                    otpInputs[index + 1].focus();
                }
            });

            // 2. Backspace focus previous
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace' && input.value.length === 0 && index > 0) {
                    otpInputs[index - 1].focus();
                }
            });

            // 3. Numeric only
            input.addEventListener('keypress', function (e) {
                const charCode = (e.which) ? e.which : e.keyCode;
                if (charCode > 31 && (charCode < 48 || charCode > 57)) {
                    e.preventDefault();
                }
            });
        });
    }

    // === Step 1: Request OTP ===
    if (phoneForm) {
        phoneForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            userPhone = phoneInput.value.trim();

            if (userPhone.length < 10) {
                showToast ? showToast("Please enter a valid phone number", "error") : alert("Invalid Phone");
                return;
            }

            const btn = phoneForm.querySelector('button');
            const originalText = btn.innerText;
            btn.disabled = true;
            btn.innerText = "Sending...";

            try {
                // Corrected Path: /auth/otp/send/ (Assuming standard /api/v1/auth/ prefix)
                await apiCall('/auth/otp/send/', 'POST', { 
                    phone: userPhone,
                    role: 'CUSTOMER' 
                }, false); 

                // UI Transition
                if (window.showToast) showToast("OTP Sent!", "success");
                phoneForm.style.display = 'none';
                otpForm.style.display = 'block';
                document.getElementById('display-phone').innerText = userPhone;
                
                if(otpInputs.length > 0) otpInputs[0].focus();

            } catch (error) {
                console.error("OTP Error:", error);
                const msg = error.message || "Failed to send OTP";
                showToast ? showToast(msg, "error") : alert(msg);
                btn.disabled = false;
                btn.innerText = originalText;
            }
        });
    }

    // === Step 2: Verify OTP ===
    if (otpForm) {
        otpForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            let otpCode = '';
            otpInputs.forEach(input => otpCode += input.value);

            if (otpCode.length !== 6) {
                showToast ? showToast("Please enter 6-digit OTP", "warning") : alert("Enter 6-digit OTP");
                return;
            }

            const btn = otpForm.querySelector('button');
            const originalText = btn.innerText;
            btn.innerText = "Verifying...";
            btn.disabled = true;

            try {
                const response = await apiCall('/auth/otp/login/', 'POST', {
                    phone: userPhone,
                    otp: otpCode,
                    role: 'CUSTOMER',
                    device_id: navigator.userAgent
                }, false);

                // Securely Store Session Data
                localStorage.setItem('access_token', response.access);
                localStorage.setItem('refresh_token', response.refresh);
                localStorage.setItem('user', JSON.stringify(response.user));
                
                // Update Global Config (Runtime update)
                if (window.APP_CONFIG) {
                    window.APP_CONFIG.IS_LOGGED_IN = true;
                    window.APP_CONFIG.USER = response.user;
                }

                showToast ? showToast("Login Successful!", "success") : null;

                // Redirect using Central Config
                const redirectUrl = (window.APP_CONFIG && window.APP_CONFIG.URLS) 
                    ? window.APP_CONFIG.URLS.HOME 
                    : '/index.html';
                
                setTimeout(() => {
                    window.location.href = redirectUrl;
                }, 500);

            } catch (error) {
                console.error("Login Error:", error);
                const msg = error.message || "Invalid OTP";
                showToast ? showToast(msg, "error") : alert(msg);
                btn.innerText = originalText;
                btn.disabled = false;
            }
        });
    }

    // Edit Phone Link
    const editPhoneBtn = document.getElementById('edit-phone');
    if(editPhoneBtn){
        editPhoneBtn.addEventListener('click', () => {
            otpForm.style.display = 'none';
            phoneForm.style.display = 'block';
            const btn = phoneForm.querySelector('button');
            btn.disabled = false;
            btn.innerText = "Get OTP";
            // Clear OTP fields
            otpInputs.forEach(i => i.value = '');
        });
    }
});