// static/assets/js/utils/home.js

document.addEventListener('DOMContentLoaded', async () => {
    await loadCategories();
    await loadFeaturedProducts(); // Now Active
});

async function loadCategories() {
    const navContainer = document.getElementById('dynamic-navbar');
    const gridContainer = document.getElementById('home-category-grid');

    try {
        const response = await apiCall('/catalog/categories/?page_size=100', 'GET', null, false);
        const categories = response.results || response;
        const parents = categories.filter(c => c.parent === null);

        // Navbar Update
        if (navContainer) {
            navContainer.innerHTML = '<a href="/" class="nav-item active">All</a>';
            parents.slice(0, 8).forEach(cat => { // Limit to 8 for nav
                const link = document.createElement('a');
                link.href = `/search_results.html?slug=${cat.slug}`;
                link.className = 'nav-item';
                link.innerText = getCleanName(cat.name);
                navContainer.appendChild(link);
            });
        }

        // Home Grid Update
        if (gridContainer) {
            gridContainer.innerHTML = '';
            parents.slice(0, 8).forEach(cat => { // Limit for home grid
                const div = document.createElement('div');
                div.className = 'cat-item-home';
                div.onclick = () => window.location.href = `/search_results.html?slug=${cat.slug}`;
                const icon = cat.icon_url || 'https://cdn-icons-png.flaticon.com/512/3759/3759344.png';
                div.innerHTML = `
                    <div class="cat-icon-box"><img src="${icon}" alt="${cat.name}"></div>
                    <span class="cat-label">${getCleanName(cat.name)}</span>
                `;
                gridContainer.appendChild(div);
            });
        }
    } catch (error) {
        console.error("Error loading categories:", error);
    }
}

async function loadFeaturedProducts() {
    const container = document.getElementById('home-featured-products');
    if (!container) return;

    container.innerHTML = '<div class="loader"></div>';

    try {
        // Fetch products where is_featured=true
        const response = await apiCall('/catalog/skus/?is_featured=true&page_size=10', 'GET', null, false);
        const products = response.results || response;

        container.innerHTML = '';

        if (products.length === 0) {
            container.innerHTML = '<p class="text-muted">No featured items today.</p>';
            return;
        }

        products.forEach(p => {
            const card = document.createElement('div');
            // Reusing prod-card class from catalog.css
            card.className = 'prod-card'; 
            card.style.minWidth = '160px'; // Ensure width in horizontal scroll

            const imgUrl = p.image_url || 'https://cdn-icons-png.flaticon.com/512/1147/1147805.png';
            
            card.innerHTML = `
                <div class="prod-img-box">
                    <img src="${imgUrl}" class="prod-img" alt="${p.name}">
                </div>
                <div class="prod-title">${p.name}</div>
                <div class="prod-unit">${p.unit}</div>
                <div class="prod-footer">
                    <div class="prod-price">₹${parseFloat(p.sale_price).toFixed(0)}</div>
                    <a href="/product.html?code=${p.sku_code}" class="prod-add-btn" style="text-decoration:none;">VIEW</a>
                </div>
            `;
            container.appendChild(card);
        });

    } catch (e) {
        console.error("Featured Load Error:", e);
        container.innerHTML = '';
    }
}

function getCleanName(fullName) {
    const map = {
        "Groceries & Essentials": "Groceries",
        "Fresh Produce": "Fruits & Veg",
        "Snacks & Beverages": "Snacks",
        "Dairy, Bread & Eggs": "Dairy",
        "Personal Care": "Self Care",
    };
    return map[fullName] || fullName.split(' ')[0].replace(',', '');
}