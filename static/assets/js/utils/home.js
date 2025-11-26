// assets/js/utils/home.js

document.addEventListener('DOMContentLoaded', () => {
    loadCategories();
    loadFeaturedProducts();
});

async function loadCategories() {
    const container = document.querySelector('.categories');
    if(!container) return;

    try {
        // Backend call
        const categories = await apiCall('/catalog/categories/');
        
        // HTML generation
        container.innerHTML = categories.map(cat => `
            <a href="category.html?slug=${cat.slug}" class="category-card">
                <div class="category-icon">
                    ${cat.icon_url ? `<img src="${cat.icon_url}" style="width:100%; height:100%; object-fit:cover; border-radius:50%;">` : '<i class="fas fa-shopping-basket"></i>'}
                </div>
                <h3>${cat.name}</h3>
            </a>
        `).join('');
    } catch (e) {
        console.error("Categories Load Error", e);
    }
}

async function loadFeaturedProducts() {
    const grid = document.querySelector('.product-grid');
    if(!grid) return;

    try {
        // Fetching featured products
        const products = await apiCall('/catalog/skus/?is_featured=true');
        
        if(products.length === 0) {
            grid.innerHTML = '<p style="padding:10px;">No featured products today.</p>';
            return;
        }

        grid.innerHTML = products.map(p => {
            const imgUrl = p.image_url ? p.image_url : 'https://via.placeholder.com/150?text=No+Image';
            
            return `
            <div class="product-card">
                <a href="product.html?code=${p.sku_code}">
                    <div class="product-image">
                        ${p.is_featured ? '<div class="discount-badge">Hot</div>' : ''}
                        <img src="${imgUrl}" alt="${p.name}">
                    </div>
                </a>
                <div class="product-info">
                    <h3 class="product-title">${p.name}</h3>
                    <div class="product-weight">${p.unit}</div>
                    <div class="product-price">
                        <div class="price">₹${parseFloat(p.sale_price).toFixed(0)}</div>
                        <button class="add-to-cart" onclick="addToCart('${p.id}')">
                            <i class="fas fa-plus"></i>
                        </button>
                    </div>
                </div>
            </div>`;
        }).join('');

    } catch (e) {
        grid.innerHTML = '<p>Failed to load products.</p>';
        console.error(e);
    }
}

// Global Add to Cart
window.addToCart = async function(skuId) {
    if (!isLoggedIn()) {
        window.location.href = 'auth.html';
        return;
    }
    try {
        // Quantity 1 add kar rahe hain
        await apiCall('/orders/cart/add/', 'POST', { sku_id: skuId, quantity: 1 }, true);
        alert("Added to cart!");
        updateGlobalCartCount();
    } catch (e) {
        alert("Error: " + e.message);
    }
};