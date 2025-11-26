// assets/js/auth.js

document.addEventListener('DOMContentLoaded', () => {
    const phoneForm = document.getElementById('phone-form');
    const otpForm = document.getElementById('otp-form');
    const phoneInput = document.getElementById('phone');
    const verifyBtn = document.getElementById('verify-btn');
    const otpBoxes = document.querySelectorAll('.otp-box');
    const phoneDisplay = document.getElementById('phone-display');
    
    let userPhone = "";

    // --- 1. Send OTP ---
    if(phoneForm) {
        phoneForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const phoneVal = phoneInput.value.trim();

            if (phoneVal.length !== 10) {
                alert("Please enter a valid 10-digit number");
                return;
            }

            const submitBtn = phoneForm.querySelector('.submit-btn');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<div class="spinner"></div> Sending...';
            submitBtn.disabled = true;

            try {
                // API: Request OTP (Customer)
                const resp = await apiCall('/auth/customer/request-otp/', 'POST', {
                    phone: phoneVal
                });

                // Dev mode mein OTP alert karein (testing ke liye)
                if(resp.dev_hint) alert("OTP is: " + resp.dev_hint);

                userPhone = phoneVal;
                phoneDisplay.innerText = `+91 ${userPhone}`;
                
                phoneForm.style.display = 'none';
                otpForm.style.display = 'block';
                otpBoxes[0].focus();

            } catch (error) {
                alert(error.message);
            } finally {
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }
        });
    }

    // --- 2. Verify OTP ---
    if(otpForm) {
        otpForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const otpCode = Array.from(otpBoxes).map(box => box.value).join('');
            
            if (otpCode.length !== 6) {
                alert("Enter full 6-digit OTP");
                return;
            }

            const originalText = verifyBtn.innerHTML;
            verifyBtn.innerHTML = '<div class="spinner"></div> Verifying...';
            verifyBtn.disabled = true;

            try {
                // API: Verify OTP
                const data = await apiCall('/auth/customer/verify-otp/', 'POST', {
                    phone: userPhone,
                    otp: otpCode
                });

                // Token Save
                localStorage.setItem('accessToken', data.access);
                localStorage.setItem('refreshToken', data.refresh);
                if(data.user) localStorage.setItem('user', JSON.stringify(data.user));

                // Redirect
                window.location.href = 'index.html';

            } catch (error) {
                alert(error.message);
                verifyBtn.disabled = false;
                verifyBtn.innerHTML = originalText;
            }
        });
    }

    // OTP Box Auto-Focus
    otpBoxes.forEach((box, index) => {
        box.addEventListener('input', (e) => {
            if (e.target.value && index < otpBoxes.length - 1) otpBoxes[index + 1].focus();
        });
        box.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && !e.target.value && index > 0) otpBoxes[index - 1].focus();
        });
    });
});