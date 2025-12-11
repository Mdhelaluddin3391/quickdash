// static/assets/js/pages/auth/login.js

document.addEventListener('DOMContentLoaded', () => {
    const phoneForm = document.getElementById('phone-form');
    const otpForm = document.getElementById('otp-form');
    const phoneInput = document.getElementById('phone');
    
    let userPhone = '';

    // Step 1: Request OTP
    phoneForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        userPhone = phoneInput.value;

        // Basic validation
        if (userPhone.length < 10) {
            alert("Please enter a valid phone number");
            return;
        }

        const btn = phoneForm.querySelector('button');
        btn.disabled = true;
        btn.innerText = "Sending...";

        try {
            // FIX: Correct Endpoint & Add ROLE parameter
            // Endpoint matches apps/accounts/urls.py: path('auth/otp/send/', ...)
            await apiCall('/auth/auth/otp/send/', 'POST', { 
                phone: userPhone,
                role: 'CUSTOMER' // Required by backend
            }, false); 

            // Switch UI to OTP Form
            phoneForm.style.display = 'none';
            otpForm.style.display = 'block';
            document.getElementById('display-phone').innerText = userPhone;
            
            // alert("OTP Sent! (Check Server Console in Dev Mode)");

        } catch (error) {
            alert(error.message);
            btn.disabled = false;
            btn.innerText = "Get OTP";
        }
    });

    // Step 2: Verify OTP
    otpForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        let otpCode = '';
        document.querySelectorAll('.otp-field').forEach(input => {
            otpCode += input.value;
        });

        if (otpCode.length !== 6) {
            alert("Please enter 6-digit OTP");
            return;
        }

        const btn = otpForm.querySelector('button');
        btn.innerText = "Verifying...";

        try {
            // FIX: Correct Endpoint & Add ROLE parameter
            // Endpoint matches apps/accounts/urls.py: path('auth/otp/login/', ...)
            const response = await apiCall('/auth/auth/otp/login/', 'POST', {
                phone: userPhone,
                otp: otpCode,
                role: 'CUSTOMER', // Required by backend
                device_id: navigator.userAgent // Optional but good for tracking
            }, false);

            // Store Tokens (DRF SimpleJWT returns 'access' and 'refresh')
            localStorage.setItem('access_token', response.access);
            localStorage.setItem('refresh_token', response.refresh);
            localStorage.setItem('user', JSON.stringify(response.user));

            // Redirect to Home
            window.location.href = '/index.html'; 

        } catch (error) {
            console.error(error);
            alert(error.message || "Invalid OTP");
            btn.innerText = "Verify & Login";
        }
    });

    // Edit Phone Link
    const editPhoneBtn = document.getElementById('edit-phone');
    if(editPhoneBtn){
        editPhoneBtn.addEventListener('click', () => {
            otpForm.style.display = 'none';
            phoneForm.style.display = 'block';
            const btn = phoneForm.querySelector('button');
            btn.disabled = false;
            btn.innerText = "Get OTP";
        });
    }
});