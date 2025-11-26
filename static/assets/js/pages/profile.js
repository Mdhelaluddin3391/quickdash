document.addEventListener('DOMContentLoaded', () => {
    const navItems = document.querySelectorAll('.profile-nav li');
    const contentSections = document.querySelectorAll('.profile-content-section');
    
    // --- Tab Switching Logic ---
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            const targetId = item.getAttribute('data-content');
            if (targetId) {
                e.preventDefault(); 
                navItems.forEach(i => i.classList.remove('active'));
                contentSections.forEach(s => s.classList.remove('active'));
                item.classList.add('active');
                const targetSection = document.getElementById(targetId);
                if (targetSection) {
                    targetSection.classList.add('active');
                }
            }
        });
    });

    // --- Modal Logic ---

    // Rating Modal
    const ratingModal = document.getElementById('rating-modal');
    const closeRatingModal = document.getElementById('close-rating-modal');
    // Note: rateButtons dynamic content ke liye 'utils/profile.js' mein handle honge,
    // lekin static elements ke liye yahan listener lagaye ja sakte hain.

    if(closeRatingModal && ratingModal) {
        closeRatingModal.addEventListener('click', () => {
            ratingModal.style.display = 'none';
        });
    }

    // Address Modal
    const addressModal = document.getElementById('address-modal');
    const showAddressModalBtn = document.getElementById('show-address-modal');
    const closeAddressModal = document.getElementById('close-address-modal');

    if(showAddressModalBtn && addressModal) {
        showAddressModalBtn.addEventListener('click', () => {
            addressModal.style.display = 'flex';
        });
    }

    if(closeAddressModal && addressModal) {
        closeAddressModal.addEventListener('click', () => {
            addressModal.style.display = 'none';
        });
    }

    // Overlay Click Close
    window.addEventListener('click', (e) => {
        if (e.target === ratingModal) {
            ratingModal.style.display = 'none';
        }
        if (e.target === addressModal) {
            addressModal.style.display = 'none';
        }
    });
});