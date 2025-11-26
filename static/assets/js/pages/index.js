// assets/js/pages/index.js

document.addEventListener('DOMContentLoaded', () => {

    // 1. Search Bar Logic
    const input = document.querySelector('.search-bar-row input');
    const searchBar = document.querySelector('.search-bar-row');
    if (input && searchBar) {
        // Focus: Jab click karein
        input.addEventListener('focus', () => {
            searchBar.style.backgroundColor = '#fff';
        });
        // Blur: Jab kahin aur click karein
        input.addEventListener('blur', () => {
            searchBar.style.backgroundColor = 'var(--light)';
        });
    }

    // 2. Promo Card Auto-Swipe Logic
    const scrollBanner = document.querySelector('.scroll-banner');
    if (scrollBanner) {
        let currentCardIndex = 0;
        const promoCards = scrollBanner.querySelectorAll('.promo-card');
        if (promoCards.length > 1) {
            setInterval(() => {
                currentCardIndex = (currentCardIndex + 1) % promoCards.length;
                const nextCard = promoCards[currentCardIndex];
                
                // Card ke left position tak scroll karein
                scrollBanner.scroll({
                    left: nextCard.offsetLeft,
                    behavior: 'smooth'
                });
            }, 3000); // Har 3 second mein
        }
    }

    // 3. Cart Animation Logic (Updated for Dynamic Elements)
    // Event Delegation use kar rahe hain taaki API se load hue buttons par bhi click chale
    document.addEventListener('click', (e) => {
        // Check karein ki click 'add-to-cart' button ya uske icon par hua hai
        const btn = e.target.closest('.add-to-cart');
        
        if (btn) {
            const cartCountElement = document.querySelector('.cart-count');
            if(cartCountElement) {
                // Button ko animate karein
                cartCountElement.style.transform = 'scale(1.3)';
                setTimeout(() => {
                    cartCountElement.style.transform = 'scale(1)';
                }, 200);
            }
        }
    });

});