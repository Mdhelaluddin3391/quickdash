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

        if (userPhone.length < 10) {
            alert("Please enter a valid phone number");
            return;
        }

        const btn = phoneForm.querySelector('button');
        btn.disabled = true;
        btn.innerText = "Sending...";

        try {
            // Backend API Call
            await apiCall('/auth/customer/request-otp/', 'POST', { 
                phone: userPhone 
            }, false); 

            // UI Switch
            phoneForm.style.display = 'none';
            otpForm.style.display = 'block';
            document.getElementById('display-phone').innerText = userPhone;
            
            alert("OTP Sent! (Dev Mode: Check Console/Terminal)");

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
            const response = await apiCall('/auth/customer/verify-otp/', 'POST', {
                phone: userPhone,
                otp: otpCode
            }, false);

            // [FIX HERE] Sahi Keys use karein ('access_token' instead of 'accessToken')
            localStorage.setItem('access_token', response.access);
            localStorage.setItem('refresh_token', response.refresh);
            localStorage.setItem('user', JSON.stringify(response.user));

            window.location.href = '/'; 

        } catch (error) {
            alert(error.message);
            btn.innerText = "Verify & Login";
        }
    });

    // Edit Phone Link
    document.getElementById('edit-phone').addEventListener('click', () => {
        otpForm.style.display = 'none';
        phoneForm.style.display = 'block';
        phoneForm.querySelector('button').disabled = false;
        phoneForm.querySelector('button').innerText = "Get OTP";
    });
});