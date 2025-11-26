document.addEventListener('DOMContentLoaded', function() {
    // Cart count update logic is handled globally in api.js or cart.js util
    
    // Category Page Specific: Sidebar Toggle Logic
    const sidebarItems = document.querySelectorAll('.sidebar-nav li');
    if(sidebarItems.length > 0) {
        sidebarItems.forEach(item => {
            item.addEventListener('click', function(e) {
                // e.preventDefault(); // Optional: agar link na ho
                sidebarItems.forEach(i => i.classList.remove('active'));
                this.classList.add('active');
            });
        });
    }
    
    // Note: Cart Page items loading is handled by assets/js/utils/cart.js
});