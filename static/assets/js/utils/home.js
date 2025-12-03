// static/assets/js/utils/home.js

document.addEventListener('DOMContentLoaded', async () => {
    await loadHomeData();
});

async function loadHomeData() {
    const navContainer = document.getElementById('dynamic-navbar');
    const gridContainer = document.getElementById('home-category-grid');
    const sectionsContainer = document.getElementById('dynamic-sections-container');

    try {
        // 1. Fetch All Parent Categories
        const response = await apiCall('/catalog/categories/?page_size=100', 'GET', null, false);
        const allCats = response.results || response;
        const parentCats = allCats.filter(c => c.parent === null);

        // --- A. Update Navbar & Top Grid ---
        if (navContainer) {
            navContainer.innerHTML = '<a href="/" class="nav-item active">All</a>';
            gridContainer.innerHTML = ''; // Clear loader

            // Fallback: Agar category bhi nahi hai, toh static dikhao grid mein
            if (parentCats.length === 0) {
                gridContainer.innerHTML = '<p class="text-muted text-center col-12" style="grid-column: 1/-1;">Categories Coming Soon...</p>';
            }

            parentCats.forEach((cat, index) => {
                // Navbar (Limit 8)
                if (index < 8) {
                    const link = document.createElement('a');
                    link.href = `/search_results.html?slug=${cat.slug}`;
                    link.className = 'nav-item';
                    link.innerText = getCleanName(cat.name);
                    navContainer.appendChild(link);
                }

                // Top Grid (Limit 8)
                if (index < 8) {
                    const div = document.createElement('div');
                    div.className = 'cat-item-home';
                    div.onclick = () => window.location.href = `/search_results.html?slug=${cat.slug}`;
                    const icon = cat.icon_url || 'https://cdn-icons-png.flaticon.com/512/3759/3759344.png';
                    div.innerHTML = `
                        <div class="cat-icon-box"><img src="${icon}" alt="${cat.name}"></div>
                        <span class="cat-label">${getCleanName(cat.name)}</span>
                    `;
                    gridContainer.appendChild(div);
                }
            });
        }

        // --- B. Build Dynamic Product Rows (Shelves) ---
        if (sectionsContainer) {
            sectionsContainer.innerHTML = ''; // Clear loader

            // Sirf pehli 8 categories fetch karte hain
            const catsToLoad = parentCats.slice(0, 8); 

            // Parallel Fetching for Speed
            const promises = catsToLoad.map(cat => loadCategoryShelf(cat));
            const shelves = await Promise.all(promises);

            // Append valid shelves
            shelves.forEach(html => {
                if (html) sectionsContainer.innerHTML += html;
            });

            // ✅ [UPDATED] STATIC FALLBACK LOGIC
            // Agar koi bhi real product shelf nahi bani, toh ye Dummy Shelf dikhao
            if (sectionsContainer.innerHTML === '') {
                sectionsContainer.innerHTML = `
                    <section class="category-section">
                        <div class="section-header">
                            <h3>Best Sellers (Demo)</h3>
                            <a href="#" class="view-all-btn" style="pointer-events:none; color:#999;">View All</a>
                        </div>
                        <div class="product-scroll-wrapper">
                            <div class="prod-card">
                                <div class="prod-img-box">
                                    <img src="https://cdn-icons-png.flaticon.com/512/2553/2553691.png" class="prod-img" alt="Chips">
                                </div>
                                <div class="prod-title">Classic Salted Chips</div>
                                <div class="prod-unit">50g</div>
                                <div class="prod-footer">
                                    <div class="prod-price">₹20</div>
                                    <button class="btn-add-sm" onclick="alert('This is a demo item. Add real products from Admin Panel.')">ADD</button>
                                </div>
                            </div>

                            <div class="prod-card">
                                <div class="prod-img-box">
                                    <img src="https://cdn-icons-png.flaticon.com/512/2909/2909787.png" class="prod-img" alt="Cola">
                                </div>
                                <div class="prod-title">Cola Soft Drink</div>
                                <div class="prod-unit">330ml</div>
                                <div class="prod-footer">
                                    <div class="prod-price">₹40</div>
                                    <button class="btn-add-sm" onclick="alert('This is a demo item.')">ADD</button>
                                </div>
                            </div>

                            <div class="prod-card">
                                <div class="prod-img-box">
                                    <img src="https://cdn-icons-png.flaticon.com/512/5029/5029236.png" class="prod-img" alt="Bread">
                                </div>
                                <div class="prod-title">Whole Wheat Bread</div>
                                <div class="prod-unit">400g</div>
                                <div class="prod-footer">
                                    <div class="prod-price">₹45</div>
                                    <button class="btn-add-sm" onclick="alert('This is a demo item.')">ADD</button>
                                </div>
                            </div>

                             <div class="prod-card">
                                <div class="prod-img-box">
                                    <img src="https://cdn-icons-png.flaticon.com/512/2329/2329865.png" class="prod-img" alt="Veg">
                                </div>
                                <div class="prod-title">Fresh Farm Tomato</div>
                                <div class="prod-unit">1kg</div>
                                <div class="prod-footer">
                                    <div class="prod-price">₹30</div>
                                    <button class="btn-add-sm" onclick="alert('This is a demo item.')">ADD</button>
                                </div>
                            </div>

                            <div class="prod-card">
                                <div class="prod-img-box">
                                    <img src="https://cdn-icons-png.flaticon.com/512/2921/2921822.png" class="prod-img" alt="Milk">
                                </div>
                                <div class="prod-title">Fresh Cow Milk</div>
                                <div class="prod-unit">1L Pouch</div>
                                <div class="prod-footer">
                                    <div class="prod-price">₹65</div>
                                    <button class="btn-add-sm" onclick="alert('This is a demo item.')">ADD</button>
                                </div>
                            </div>
                        </div>
                        <div class="text-center pb-3">
                            <small class="text-muted" style="font-size:0.75rem;">* No real products found. Showing demo items.</small>
                        </div>
                    </section>
                `;
            }
        }

    } catch (error) {
        console.error("Home Load Error:", error);
        if(sectionsContainer) sectionsContainer.innerHTML = '<p class="text-center text-danger py-4">Could not load products.</p>';
    }
}

/**
 * Fetches products for a category and returns HTML string for the shelf
 */
async function loadCategoryShelf(cat) {
    try {
        // Fetch 10 items for this category
        const res = await apiCall(`/catalog/skus/?category__slug=${cat.slug}&page_size=10`, 'GET', null, false);
        const products = res.results || res;

        if (!products || products.length === 0) return null;

        // Generate HTML for products
        const cardsHtml = products.map(p => {
            const imgUrl = p.image_url || 'https://cdn-icons-png.flaticon.com/512/1147/1147805.png';
            const price = parseFloat(p.sale_price).toFixed(0);
            
            return `
                <div class="prod-card">
                    <a href="/product.html?code=${p.sku_code}" style="text-decoration:none; color:inherit;">
                        <div class="prod-img-box">
                            <img src="${imgUrl}" class="prod-img" alt="${p.name}">
                        </div>
                        <div class="prod-title">${p.name}</div>
                        <div class="prod-unit">${p.unit}</div>
                    </a>
                    <div class="prod-footer">
                        <div class="prod-price">₹${price}</div>
                        <button class="btn-add-sm" onclick="addToCart('${p.id}', this)">ADD</button>
                    </div>
                </div>
            `;
        }).join('');

        // Return Full Section HTML
        return `
            <section class="category-section">
                <div class="section-header">
                    <h3>${cat.name}</h3>
                    <a href="/search_results.html?slug=${cat.slug}" class="view-all-btn">See All</a>
                </div>
                <div class="product-scroll-wrapper">
                    ${cardsHtml}
                </div>
            </section>
        `;

    } catch (e) {
        console.warn(`Failed to load shelf for ${cat.name}`, e);
        return null;
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

// Add to Cart Logic
async function addToCart(skuId, btn) {
    if (!APP_CONFIG.IS_LOGGED_IN) {
        window.location.href = '/auth.html';
        return;
    }
    
    const originalText = btn.innerText;
    btn.innerText = "..";
    btn.disabled = true;

    try {
        await apiCall('/orders/cart/add/', 'POST', { sku_id: skuId, quantity: 1 }, true);
        btn.innerText = "✔";
        btn.style.background = "#32CD32";
        btn.style.color = "#fff";
        
        if(window.updateGlobalCartCount) window.updateGlobalCartCount();

        setTimeout(() => {
            btn.innerText = "ADD";
            btn.style.background = "#e6f7ef";
            btn.style.color = "#32CD32";
            btn.disabled = false;
        }, 2000);

    } catch (e) {
        alert(e.message || "Failed to add");
        btn.innerText = originalText;
        btn.disabled = false;
    }
}