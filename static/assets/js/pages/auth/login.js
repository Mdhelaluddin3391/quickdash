// static/assets/js/pages/auth/login.js

document.addEventListener('DOMContentLoaded', () => {
    const phoneForm = document.getElementById('phone-form');
    const otpForm = document.getElementById('otp-form');
    const phoneInput = document.getElementById('phone');
    
    let userPhone = '';

    // === OTP Auto-Focus Logic ===
    const otpInputs = document.querySelectorAll('.otp-field');

    otpInputs.forEach((input, index) => {
        // 1. नंबर डालते ही अगले बॉक्स पर फोकस करें
        input.addEventListener('input', (e) => {
            if (input.value.length === 1) {
                if (index < otpInputs.length - 1) {
                    otpInputs[index + 1].focus();
                }
            }
        });

        // 2. बैकस्पेस दबाने पर पिछले बॉक्स पर आएं
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && input.value.length === 0) {
                if (index > 0) {
                    otpInputs[index - 1].focus();
                }
            }
        });

        // 3. सिर्फ नंबर ही अलाऊ करें
        input.addEventListener('keypress', function (e) {
            const charCode = (e.which) ? e.which : e.keyCode;
            if (charCode > 31 && (charCode < 48 || charCode > 57)) {
                e.preventDefault();
            }
        });
    }); // <--- यह Closing Bracket मिसिंग था, जो अब लगा दिया गया है।


    // === Step 1: Request OTP ===
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
            await apiCall('/auth/auth/otp/send/', 'POST', { 
                phone: userPhone,
                role: 'CUSTOMER' 
            }, false); 

            // Switch UI to OTP Form
            phoneForm.style.display = 'none';
            otpForm.style.display = 'block';
            document.getElementById('display-phone').innerText = userPhone;
            
            // Focus on first OTP input
            otpInputs[0].focus();

        } catch (error) {
            alert(error.message);
            btn.disabled = false;
            btn.innerText = "Get OTP";
        }
    });

    // === Step 2: Verify OTP ===
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
            const response = await apiCall('/auth/auth/otp/login/', 'POST', {
                phone: userPhone,
                otp: otpCode,
                role: 'CUSTOMER',
                device_id: navigator.userAgent
            }, false);

            // Store Tokens
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