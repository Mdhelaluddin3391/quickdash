document.addEventListener('DOMContentLoaded', function() {
    // UI Interactions for Checkout (Visual Selection)
    
    // Address selection (Static items ke liye, dynamic utils/checkout.js sambhalega)
    const addressCards = document.querySelectorAll('.address-card');
    addressCards.forEach(card => {
        card.addEventListener('click', function() {
            const radio = this.querySelector('input[type="radio"]');
            if (radio) {
                radio.checked = true;
                addressCards.forEach(c => c.classList.remove('selected'));
                this.classList.add('selected');
            }
        });
    });
    
    // Payment method selection
    const paymentOptions = document.querySelectorAll('.payment-option');
    paymentOptions.forEach(option => {
        option.addEventListener('click', function() {
            const radio = this.querySelector('input[type="radio"]');
            if (radio) {
                radio.checked = true;
                paymentOptions.forEach(o => o.classList.remove('selected'));
                this.classList.add('selected');
            }
        });
    });
    
    // Add new address button (UI stub)
    const addAddressBtn = document.querySelector('.add-new-address-btn');
    if(addAddressBtn) {
        addAddressBtn.addEventListener('click', function() {
            // In future this can open a modal
            // window.location.href = 'profile.html#addresses';
        });
    }
});