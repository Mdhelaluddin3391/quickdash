document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    const skuCode = params.get('code');

    if (!skuCode) {
        alert("Product not found");
        window.location.href = '/';
        return;
    }

    try {
        const product = await apiCall(`/catalog/skus/${skuCode}/`);
        
        // Populate DOM
        document.getElementById('p-name').innerText = product.name;
        document.getElementById('p-brand').innerText = product.brand_name || 'QuickDash';
        document.getElementById('p-unit').innerText = product.unit;
        document.getElementById('p-price').innerText = `₹${parseFloat(product.sale_price).toFixed(0)}`;
        document.getElementById('p-desc').innerText = product.description || "No description available.";
        
        const img = document.getElementById('p-image');
        img.src = product.image_url || 'https://via.placeholder.com/300?text=No+Image';

        if(product.is_featured) {
            document.getElementById('p-badge').innerText = "BESTSELLER";
        }

        // Add to Cart Logic
        const addBtn = document.getElementById('add-to-cart-btn');
        addBtn.onclick = () => addToCart(product.id);

    } catch (e) {
        console.error(e);
        document.getElementById('product-content').innerHTML = 
            '<div style="padding:40px; text-align:center;">Product not found.</div>';
    }
});

async function addToCart(skuId) {
    if (!APP_CONFIG.IS_LOGGED_IN) {
        window.location.href = '/auth.html';
        return;
    }
    const btn = document.getElementById('add-to-cart-btn');
    const originalText = btn.innerText;
    
    btn.disabled = true;
    btn.innerText = "ADDING...";

    try {
        await apiCall('/orders/cart/add/', 'POST', { sku_id: skuId, quantity: 1 }, true);
        btn.innerText = "ADDED ✔";
        setTimeout(() => btn.innerText = originalText, 2000);
        if(window.updateGlobalCartCount) window.updateGlobalCartCount();
    } catch (e) {
        alert(e.message);
        btn.innerText = originalText;
    } finally {
        btn.disabled = false;
    }
}