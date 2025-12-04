// static/assets/js/utils/home.js

// --- Global Variables for Infinite Scroll ---
let parentCategories = []; // Saari main categories yahan store hongi
let loadedCount = 0;       // Abhi tak kitni categories screen par dikh chuki hain
const BATCH_SIZE = 3;      // Ek baar mein kitni category load karni hain (3-3 karke)
let isLoadingShelves = false; // Flag taaki double loading na ho
let shelfObserver;         // Observer ko global scope mein rakhein

document.addEventListener('DOMContentLoaded', async () => {
    console.log("Loading initial data sequentially...");

    await loadBanners();
    await loadHomeCategories();
    await loadFlashSales();
    await loadBrands();
    initProductShelves();

    console.log("All initial data loaded sequentially.");
});


// =========================================================
// 1. HERO BANNERS
// =========================================================
async function loadBanners() {
    const slider = document.getElementById('hero-slider');
    const midContainer = document.getElementById('mid-banner-container');

    try {
        const response = await apiCall('/catalog/banners/', 'GET', null, false);
        const banners = response.results || response;
        
        // A. Hero Slider
        const heroBanners = banners.filter(b => b.position === 'HERO');
        if (slider) {
            if (heroBanners.length > 0) {
                slider.innerHTML = heroBanners.map(b => `
                    <a href="${b.target_url}" class="promo-card" style="background: ${b.bg_gradient}">
                        <div class="promo-content">
                            <h2>${b.title}</h2>
                            <p>Click to Explore</p>
                            <span class="promo-btn">Shop Now</span>
                        </div>
                        <img src="${b.image_url}" class="promo-img" alt="${b.title}" loading="lazy">
                    </a>
                `).join('');
            } else {
                slider.innerHTML = `<div class="promo-card" style="background: linear-gradient(135deg, #32CD32, #2ecc71);">
                    <div class="promo-content"><h2>Welcome to<br>QuickDash</h2></div>
                </div>`;
            }
        }

        // B. Mid Banner
        const midBanners = banners.filter(b => b.position === 'MID');
        if (midContainer && midBanners.length > 0) {
            const mid = midBanners[0];
            midContainer.style.display = 'block';
            midContainer.innerHTML = `
                <a href="${mid.target_url}">
                    <img src="${mid.image_url}" alt="${mid.title}" loading="lazy" style="width:100%; border-radius:12px; box-shadow:0 4px 10px rgba(0,0,0,0.1);">
                </a>
            `;
        } else if (midContainer) {
            midContainer.style.display = 'none';
        }

    } catch (e) {
        console.error("Banner Error:", e);
    }
}

// =========================================================
// 2. EXPLORE CATEGORIES (TOP GRID)
// =========================================================
async function loadHomeCategories() {
    const grid = document.getElementById('home-category-grid');
    if (!grid) return;
    
    try {
        const response = await apiCall('/catalog/categories/?page_size=100', 'GET', null, false);
        const cats = response.results || response;
        
        const parents = cats.filter(c => !c.parent);

        grid.innerHTML = parents.map(c => `
            <div class="cat-item-home" onclick="window.location.href='/search_results.html?slug=${c.slug}'">
                <div class="cat-icon-box">
                    <img src="${c.icon_url || 'https://cdn-icons-png.flaticon.com/512/2921/2921822.png'}" alt="${c.name}">
                </div>
                <span class="cat-label">${c.name}</span>
            </div>
        `).join('');

    } catch (e) {
        grid.innerHTML = '<p class="text-danger text-center">Failed to load categories</p>';
        console.error("Home Category Grid Error:", e);
    }
}

// =========================================================
// 3. FLASH SALES
// =========================================================
async function loadFlashSales() {
    const container = document.getElementById('flash-sale-section');
    const grid = document.getElementById('flash-sale-grid');
    if (!container || !grid) return;
    
    try {
        const response = await apiCall('/catalog/flash-sales/', 'GET', null, false);
        const sales = response.results || response;

        if (sales.length === 0) {
            container.style.display = 'none';
            return;
        }

        container.style.display = 'block';
        if (sales[0] && sales[0].end_time) startTimer(new Date(sales[0].end_time));

        grid.innerHTML = sales.map(sale => `
            <div class="flash-card">
                <div class="badge-off">${sale.discount_percent}% OFF</div>
                <img src="${sale.sku_image || 'https://cdn-icons-png.flaticon.com/512/2553/2553691.png'}">
                <div class="f-info">
                    <div>${sale.sku_name}</div>
                    <div class="price">
                        <span>₹${parseFloat(sale.discounted_price).toFixed(0)}</span>
                        <span style="text-decoration:line-through;">₹${parseFloat(sale.original_price).toFixed(0)}</span>
                    </div>
                    <div class="flash-action-row">
                        <div class="progress-wrapper">
                            <div class="progress-bar"><div style="width:${sale.percentage_sold}%;"></div></div>
                            <small>${sale.percentage_sold}% Sold</small>
                        </div>
                        <button onclick="addToCart('${sale.sku_id}', this)">ADD</button>
                    </div>
                </div>
            </div>
        `).join('');

    } catch (e) {
        container.style.display = 'none';
        console.error("Flash Sale Error:", e);
    }
}

function startTimer(endTime) {
    const display = document.getElementById('flash-timer-display');
    if (!display) return;
    const interval = setInterval(() => {
        const now = new Date();
        const diff = endTime - now;
        if (diff <= 0) {
            display.innerText = "Ended";
            clearInterval(interval);
            return;
        }
        const h = Math.floor(diff / (1000 * 60 * 60));
        const m = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const s = Math.floor((diff % (1000 * 60)) / 1000);
        display.innerHTML = `Ends in <span class="time-box">${h}h : ${m}m : ${s}s</span>`;
    }, 1000);
}

// =========================================================
// 4. BRANDS
// =========================================================
async function loadBrands() {
    const scroller = document.getElementById('brand-scroller');
    if (!scroller) return;
    try {
        const response = await apiCall('/catalog/brands/', 'GET', null, false);
        const brands = response.results || response;
        if (brands.length === 0) return;
        scroller.innerHTML = brands.map(b => `
            <div class="brand-circle" onclick="window.location.href='/search_results.html?search=${b.name}'">
                <img src="${b.logo_url || 'https://cdn-icons-png.flaticon.com/512/888/888879.png'}" alt="${b.name}">
            </div>
        `).join('');
    } catch (e) { 
        console.error("Brand Error", e); 
    }
}

// =========================================================
// 5. SMART SHELVES (Infinite Scroll Logic)
// =========================================================

async function initProductShelves() {
    console.log("Initializing Product Shelves...");
    const container = document.getElementById('dynamic-sections-container');
    if (!container) {
        console.error("Fatal: dynamic-sections-container not found!");
        return;
    }
    
    container.innerHTML = '<div id="shelves-loader" class="text-center py-4"><div class="loader">Loading shelves...</div></div>';

    try {
        const catResponse = await apiCall('/catalog/categories/?page_size=100', 'GET', null, false);
        const allCats = catResponse.results || catResponse;
        
        parentCategories = allCats.filter(c => !c.parent);
        console.log("Parent Categories:", parentCategories);

        if (parentCategories.length === 0) {
            container.innerHTML = '<p class="text-center text-muted">No parent product categories were found. Shelves cannot be loaded.</p>';
            return;
        }
        
        console.log(`Found ${parentCategories.length} parent categories.`);
        
        // Pehla Batch Load karo
        await loadNextBatch();

        // Agar aur categories bachi hain, to Scroll Observer set up karo
        if (loadedCount < parentCategories.length) {
            setupObserver();
        }

    } catch (e) {
        console.error("Shelves Init Error:", e);
        container.innerHTML = '<p class="text-danger text-center">Failed to initialize product shelves.</p>';
    }
}

async function loadNextBatch() {
    console.log(`loadNextBatch called. isLoading: ${isLoadingShelves}, loaded: ${loadedCount}, total: ${parentCategories.length}`);
    
    if (isLoadingShelves || loadedCount >= parentCategories.length) {
        console.log("Shelf loading skipped.");
        return;
    }
    
    isLoadingShelves = true;
    console.log(`Loading next batch of shelves. Starting from index ${loadedCount}`);
    
    const container = document.getElementById('dynamic-sections-container');
    const loader = document.getElementById('shelves-loader');
    if(loader) loader.style.display = 'block';

    const batch = parentCategories.slice(loadedCount, loadedCount + BATCH_SIZE);
    console.log("Processing batch:", batch);
    
    for (const cat of batch) {
        console.log(`Rendering shelf for category: ${cat.name}`);
        await renderSingleShelf(cat, container);
    }
    console.log("Finished processing batch.");

    loadedCount += BATCH_SIZE;
    console.log(`Finished loading batch. Total loaded: ${loadedCount}`);
    
    if(loader) loader.style.display = 'none';
    isLoadingShelves = false;

    if (loadedCount >= parentCategories.length) {
        console.log("All categories loaded. Disconnecting observer.");
        if (shelfObserver) {
            shelfObserver.disconnect();
        }
    }
}

async function renderSingleShelf(cat, container) {
    console.log(`Rendering shelf for: ${cat.name}`);
    try {
        const prodResponse = await apiCall(`/catalog/skus/?category__slug=${cat.slug}&page_size=20`, 'GET', null, false);
        const products = prodResponse.results || prodResponse;

        if (products.length > 0) {
            const shelfHtml = `
                <section class="category-section">
                    <div class="section-header">
                        <h3>${cat.name}</h3>
                        <a href="/search_results.html?slug=${cat.slug}" class="view-all-btn">See All</a>
                    </div>
                    <div class="product-scroll-wrapper">
                        ${products.map(p => `
                            <div class="prod-card">
                                <a href="/product.html?code=${p.sku_code}">
                                    <div class="prod-img-box">
                                        <img src="${p.image_url || 'https://cdn-icons-png.flaticon.com/512/1147/1147805.png'}">
                                    </div>
                                    <div class="prod-title">${p.name}</div>
                                    <div class="prod-unit">${p.unit}</div>
                                </a>
                                <div class="prod-footer">
                                    <div class="prod-price">₹${parseFloat(p.sale_price).toFixed(0)}</div>
                                    <button onclick="addToCart('${p.id}', this)">ADD</button>
                                </div>
                            </div>
                        `).join('')}
                        <div class="view-all-card">
                             <a href="/search_results.html?slug=${cat.slug}">
                                <i class="fas fa-arrow-right"></i>
                             </a>
                        </div>
                    </div>
                </section>
            `;
            const loader = document.getElementById('shelves-loader');
            if (loader) {
                loader.insertAdjacentHTML('beforebegin', shelfHtml);
            } else {
                container.insertAdjacentHTML('beforeend', shelfHtml);
            }
        } else {
            console.log(`No products found for category: ${cat.name}`);
        }
    } catch (e) {
        console.warn(`Failed to load shelf for ${cat.name}`, e);
    }
}

function setupObserver() {
    const loader = document.getElementById('shelves-loader');
    if (!loader) return;

    const options = {
        root: null, // viewport
        rootMargin: '0px',
        threshold: 0.1 
    };

    shelfObserver = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && !isLoadingShelves) {
            console.log("Scroll trigger hit!");
            loadNextBatch();
        }
    }, options);

    shelfObserver.observe(loader);
    console.log("Intersection observer is set up.");
}


// =========================================================
// 6. CART LOGIC
// =========================================================
async function addToCart(skuId, btn) {
    if (!localStorage.getItem('accessToken')) {
        window.location.href = '/auth.html';
        return;
    }
    const origText = btn.innerText;
    btn.innerText = "..";
    btn.disabled = true;
    
    try {
        await apiCall('/orders/cart/add/', 'POST', { sku_id: skuId, quantity: 1 });
        btn.innerText = "✔";
        btn.style.background = "#32CD32";
        btn.style.color = "#fff";
        setTimeout(() => {
            btn.innerText = "ADD";
            btn.style.background = "#e6f7ef";
            btn.style.color = "#32CD32";
            btn.disabled = false;
        }, 1500);
        if(window.updateGlobalCartCount) window.updateGlobalCartCount();
    } catch (e) {
        alert(e.message || "Failed");
        btn.innerText = origText;
        btn.disabled = false;
    }
}