document.addEventListener('DOMContentLoaded', async () => {
    const grid = document.getElementById('product-grid');
    const titleEl = document.getElementById('page-title');
    const params = new URLSearchParams(window.location.search);
    
    // Determine filters
    const categorySlug = params.get('slug'); // from category_list
    const searchQuery = params.get('q'); // from navbar search

    let apiUrl = '/catalog/skus/';
    let title = 'All Products';

    if (categorySlug) {
        apiUrl += `?category__slug=${categorySlug}`;
        title = categorySlug.replace(/-/g, ' ').toUpperCase(); // basic formatting
    } else if (searchQuery) {
        apiUrl += `?search=${encodeURIComponent(searchQuery)}`;
        title = `Search: "${searchQuery}"`;
    }

    // Set Title
    titleEl.innerText = title;

    try {
        // Fetch Data
        const response = await apiCall(apiUrl); // Using your utility
        const products = response.results || response; // Handle DRF pagination

        // Clear Loader
        grid.innerHTML = '';

        if (products.length === 0) {
            document.getElementById('empty-state').style.display = 'block';
            return;
        }

        // Render Cards
        products.forEach(p => {
            const card = document.createElement('div');
            card.className = 'prod-card';
            
            const price = parseFloat(p.sale_price).toFixed(0);
            const imgUrl = p.image_url || 'https://via.placeholder.com/150?text=No+Image';

            card.innerHTML = `
                <div class="prod-img-box">
                    ${p.is_featured ? '<span class="prod-badge">HOT</span>' : ''}
                    <img src="${imgUrl}" class="prod-img" alt="${p.name}">
                </div>
                <div class="prod-title">${p.name}</div>
                <div class="prod-unit">${p.unit}</div>
                <div class="prod-footer">
                    <div class="prod-price">₹${price}</div>
                    <button class="prod-add-btn" onclick="addToCart('${p.id}')">ADD</button>
                </div>
                <a href="/product.html?code=${p.sku_code}" style="position:absolute; inset:0; z-index:1;"></a>
            `;
            // Note: Button needs z-index 2 to be clickable over the anchor
            const btn = card.querySelector('.prod-add-btn');
            btn.style.position = 'relative';
            btn.style.zIndex = '2';

            grid.appendChild(card);
        });

    } catch (error) {
        console.error("Failed to load products", error);
        grid.innerHTML = `<p style="color:red; text-align:center;">Error loading products.</p>`;
    }
});

// Global Add to Cart Wrapper
async function addToCart(skuId) {
    if (!localStorage.getItem('accessToken')) {
        window.location.href = '/auth.html';
        return;
    }
    try {
        await apiCall('/orders/cart/add/', 'POST', { sku_id: skuId, quantity: 1 }, true);
        alert("Item added to cart!");
        if(window.updateGlobalCartCount) window.updateGlobalCartCount();
    } catch (e) {
        alert(e.message || "Failed to add");
    }
}