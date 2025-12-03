document.addEventListener('DOMContentLoaded', () => {
    // 1. Get Order ID
    const params = new URLSearchParams(window.location.search);
    const orderId = params.get('order_id');

    if (orderId) {
        // Display ID
        const displayId = "#" + orderId.slice(0, 8).toUpperCase();
        document.getElementById('success-order-id').innerText = displayId;
        
        // Setup Track Button
        const trackBtn = document.getElementById('track-btn');
        if (trackBtn) {
            trackBtn.href = "/track_order.html?id=" + orderId;
        }
        
        // 2. Trigger Confetti (Simple CSS/JS Animation Vibe)
        triggerConfetti();
    } else {
        // Fallback
        document.getElementById('success-order-id').innerText = "Confirmed";
    }
});

function triggerConfetti() {
    // Simple visual effect using an overlay
    const colors = ['#32CD32', '#FFD700', '#FF6B6B', '#48dbfb'];
    
    for (let i = 0; i < 50; i++) {
        const confetto = document.createElement('div');
        confetto.style.position = 'fixed';
        confetto.style.width = '10px';
        confetto.style.height = '10px';
        confetto.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
        confetto.style.top = '-10px';
        confetto.style.left = Math.random() * 100 + 'vw';
        confetto.style.zIndex = '9999';
        confetto.style.opacity = Math.random();
        confetto.style.transition = `top ${Math.random() * 2 + 2}s ease-out, transform 2s linear`;
        
        document.body.appendChild(confetto);

        // Animate
        setTimeout(() => {
            confetto.style.top = '110vh';
            confetto.style.transform = `rotate(${Math.random() * 360}deg)`;
        }, 100);

        // Cleanup
        setTimeout(() => {
            confetto.remove();
        }, 4000);
    }
}