// assets/js/pages/category_detail.js

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Get Category Slug from URL
    const params = new URLSearchParams(window.location.search);
    const categorySlug = params.get('slug');

    if (!categorySlug) {
        document.querySelector('.category-title').innerText = "All Products";
        loadProducts(); // Load all if no slug
        return;
    }

    // 2. Fetch Category Details (for title) & Products
    try {
        // Parallel requests for performance
        const [categoryData, products] = await Promise.all([
            apiCall(`/catalog/categories/${categorySlug}/`),
            apiCall(`/catalog/skus/?category__slug=${categorySlug}`) // Requires FIX #2
        ]);

        // Update Header
        document.querySelector('.category-title').innerText = categoryData.name;
        document.title = `${categoryData.name} - QuickDash`;

        // Render Sidebar (Subcategories)
        if(categoryData.subcategories && categoryData.subcategories.length > 0) {
            renderSidebar(categoryData.subcategories);
        } else {
            document.querySelector('.sidebar').style.display = 'none'; // Hide if empty
        }

        // Render Products
        renderProducts(products.results || products); // DRF pagination check

    } catch (e) {
        console.error("Failed to load category data", e);
        document.querySelector('.product-grid').innerHTML = '<p>Failed to load products.</p>';
    }
});

function renderSidebar(subcategories) {
    const list = document.querySelector('.sidebar-nav');
    list.innerHTML = subcategories.map(sub => `
        <li>
            <a href="category_detail.html?slug=${sub.slug}">
                <i class="fas fa-chevron-right"></i> ${sub.name}
            </a>
        </li>
    `).join('');
}

function renderProducts(products) {
    const grid = document.querySelector('.product-grid');
    
    if (products.length === 0) {
        grid.innerHTML = '<p>No products found in this category.</p>';
        return;
    }

    grid.innerHTML = products.map(p => {
        const img = p.image_url || 'https://via.placeholder.com/200?text=No+Image';
        return `
        <div class="product-card">
            ${p.is_featured ? '<div class="product-badges"><span class="product-new">Hot</span></div>' : ''}
            
            <a href="product.html?code=${p.sku_code}" class="product-image-container">
                <img src="${img}" alt="${p.name}">
            </a>
            
            <a href="product.html?code=${p.sku_code}" class="product-name" title="${p.name}">${p.name}</a>
            <div class="product-quantity">${p.unit}</div>
            
            <div class="product-footer">
                <div class="product-price">
                    <span class="current-price">₹${parseFloat(p.sale_price).toFixed(0)}</span>
                    ${p.mrp ? `<span class="old-price">₹${p.mrp}</span>` : ''}
                </div>
                <button class="add-btn" onclick="window.addToCart('${p.id}')">
                    ADD <i class="fas fa-plus"></i>
                </button>
            </div>
        </div>
        `;
    }).join('');
}