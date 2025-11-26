document.addEventListener('DOMContentLoaded', function() {
    
    // Review Form Submit (Demo)
    const reviewForm = document.getElementById('review-form');
    if(reviewForm) {
        reviewForm.addEventListener('submit', (e) => {
            e.preventDefault();
            alert('Review submitted! It will appear after moderation.');
            reviewForm.reset();
        });
    }

    // Note: Add to Cart logic and Quantity +/- logic is handled by 
    // dynamic loading in assets/js/utils/product.js
});