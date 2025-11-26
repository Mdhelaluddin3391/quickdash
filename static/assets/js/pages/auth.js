document.addEventListener('DOMContentLoaded', () => {
    const phoneForm = document.getElementById('phone-form');
    const otpForm = document.getElementById('otp-form');
    const changeNumberLink = document.getElementById('change-number');
    const phoneDisplay = document.getElementById('phone-display');
    const verifyBtn = document.getElementById('verify-btn');
    const timerDisplay = document.getElementById('timer');
    const otpBoxes = document.querySelectorAll('.otp-box');
    
    let countdown;
    let timeLeft = 30;
    
    // Handle "Get OTP" click
    if(phoneForm) {
        phoneForm.addEventListener('submit', (e) => {
            e.preventDefault();
            
            const phoneInput = document.getElementById('phone');
            const phoneValue = phoneInput.value.trim();
            
            // Basic phone validation
            if (!/^\d{10}$/.test(phoneValue)) {
                phoneInput.parentElement.classList.add('shake');
                setTimeout(() => {
                    phoneInput.parentElement.classList.remove('shake');
                }, 300);
                phoneInput.focus();
                return;
            }
            
            // Note: Asli API call utils/auth.js handle kar raha hai.
            // Yeh sirf UI interaction ke liye hai.
        });
    }
    
    // Handle "Change" link click
    if(changeNumberLink) {
        changeNumberLink.addEventListener('click', (e) => {
            e.preventDefault();
            otpForm.style.display = 'none';
            phoneForm.style.display = 'block';
            
            // Clear timer
            if (countdown) {
                clearInterval(countdown);
            }
        });
    }
    
    // Handle OTP input behavior
    otpBoxes.forEach((box, index) => {
        box.addEventListener('input', (e) => {
            const value = e.target.value;
            
            // Auto-focus next box if value entered
            if (value && index < otpBoxes.length - 1) {
                otpBoxes[index + 1].focus();
            }
            
            // Update filled state
            if (value) {
                box.classList.add('filled');
            } else {
                box.classList.remove('filled');
            }
            
            // Enable verify button if all boxes filled
            const allFilled = Array.from(otpBoxes).every(box => box.value);
            if(verifyBtn) verifyBtn.disabled = !allFilled;
        });
        
        box.addEventListener('keydown', (e) => {
            // Handle backspace
            if (e.key === 'Backspace' && !box.value && index > 0) {
                otpBoxes[index - 1].focus();
            }
            
            // Handle arrow keys
            if (e.key === 'ArrowLeft' && index > 0) {
                otpBoxes[index - 1].focus();
            }
            if (e.key === 'ArrowRight' && index < otpBoxes.length - 1) {
                otpBoxes[index + 1].focus();
            }
        });
        
        // Prevent non-digit input
        box.addEventListener('keypress', (e) => {
            if (!/\d/.test(e.key)) {
                e.preventDefault();
            }
        });
    });
    
    // Timer function helper (Utils se call ho sakta hai)
    window.startTimerUI = function() {
        timeLeft = 30;
        if(timerDisplay) {
            timerDisplay.textContent = `${timeLeft}s`;
            
            if (countdown) clearInterval(countdown);
            
            countdown = setInterval(() => {
                timeLeft--;
                timerDisplay.textContent = `${timeLeft}s`;
                
                if (timeLeft <= 0) {
                    clearInterval(countdown);
                    timerDisplay.parentElement.innerHTML = 
                        '<a href="#" id="resend-otp">Resend OTP</a>';
                    
                    const resendLink = document.getElementById('resend-otp');
                    if(resendLink) {
                        resendLink.addEventListener('click', (e) => {
                            e.preventDefault();
                            alert('OTP Resend Triggered!'); 
                            // Yahan API call logic aayega
                            window.location.reload(); // Temporary reset
                        });
                    }
                }
            }, 1000);
        }
    }
});