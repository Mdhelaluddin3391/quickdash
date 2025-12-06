// static/assets/js/utils/home.js

// --- Global Variables for Infinite Scroll ---
let parentCategories = [];
let loadedCount = 0;
const BATCH_SIZE = 2;      // Ek baar mein 2 Categories load hongi
const PRODUCTS_PER_SHELF = 15; // Har shelf mein 15 products
let isLoadingShelves = false;
let shelfObserver;

document.addEventListener('DOMContentLoaded', async () => {
    console.log("Loading Home Page...");

    await loadBanners();
    await loadHomeCategories();
    await loadFlashSales();
    await loadBrands();

    // 2. Infinite Shelves Start Karein
    initProductShelves();

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
                        <p>Shop Now</p>
                        <span class="promo-btn">View Offers</span>
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
            midContainer.style.display = 'block';
            midContainer.innerHTML = `
            <a href="${midBanners[0].target_url}">
                <img src="${midBanners[0].image_url}" alt="Offer" loading="lazy">
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
// 2. TOP CATEGORIES (ICONS)
// =========================================================
async function loadHomeCategories() {
    const grid = document.getElementById('home-category-grid');
    if (!grid) return;

    try {
        const response = await apiCall('/catalog/categories/?page_size=100', 'GET', null, false);
        const cats = response.results || response;

        const parents = cats.filter(c => !c.parent);

        grid.innerHTML = parents.slice(0, 8).map(c => `
        <div class="cat-item-home" onclick="window.location.href='/search_results.html?slug=${c.slug}'">
            <div class="cat-icon-box">
                <img src="${c.icon_url || 'https://cdn-icons-png.flaticon.com/512/2921/2921822.png'}" alt="${c.name}">
            </div>
            <span class="cat-label">${c.name}</span>
        </div>
    `).join('');

    } catch (e) {
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
                <div style="height: 40px; overflow: hidden;">${sale.sku_name}</div>
                <div class="price">
                    <span>₹${parseFloat(sale.discounted_price).toFixed(0)}</span>
                    <span style="text-decoration:line-through; font-weight:400;">₹${parseFloat(sale.original_price).toFixed(0)}</span>
                </div>
                <button class="w-100 mt-2" style="background:#e67e22; color:white; border:none; padding:5px; border-radius:4px;" onclick="addToCart('${sale.sku_id}', this)">ADD</button>
            </div>
        </div>
    `).join('');

    } catch (e) {
        container.style.display = 'none';
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
        scroller.innerHTML = brands.map(b => `<div class="brand-circle" onclick="window.location.href='/search_results.html?search=${b.name}'"> <img src="${b.logo_url || 'https://cdn-icons-png.flaticon.com/512/888/888879.png'}" alt="${b.name}"> </div>`).join('');
    } catch (e) {
        console.error("Brand Error", e);
    }
}

// =========================================================
// 5. INFINITE SHELVES (SMART LOADING)
// =========================================================

async function initProductShelves() {
    const container = document.getElementById('dynamic-sections-container');
    if (!container) return;
    
    // Initial Loader setup
    container.innerHTML = '<div id="shelves-loader" class="text-center py-4" style="clear:both; width:100%;"><div class="loader">Loading more...</div></div>';

    try {
        // Step 1: Saari Categories ki list le aao
        const catResponse = await apiCall('/catalog/categories/?page_size=100', 'GET', null, false);
        const allCats = catResponse.results || catResponse;
        
        // Filter: Sirf Parent Categories chahiye
        parentCategories = allCats.filter(c => !c.parent);

        if (parentCategories.length === 0) {
            document.getElementById('shelves-loader').remove();
            return;
        }
        
        console.log(`Infinite Scroll: Found ${parentCategories.length} categories.`);

        // Step 2: Pehla batch load karo turant
        await loadNextBatch();

        // Step 3: Scroll Observer lagao (Infinite Scroll logic)
        setupObserver();

    } catch (e) {
        console.error("Shelves Init Error:", e);
        if(document.getElementById('shelves-loader')) {
            document.getElementById('shelves-loader').innerHTML = '<p class="text-muted text-center">End of Catalog</p>';
        }
    }
}

async function loadNextBatch() {
    // Agar loading chal rahi hai ya sab khatam ho gaya, toh ruk jao
    if (isLoadingShelves || loadedCount >= parentCategories.length) return;
    
    isLoadingShelves = true;
    
    // Loader dikhao
    let loader = document.getElementById('shelves-loader');
    if (loader) loader.style.display = 'block';

    // Agla Batch nikalo (e.g., Index 0 se 2, phir 2 se 4...)
    const batch = parentCategories.slice(loadedCount, loadedCount + BATCH_SIZE);
    
    console.log(`Loading Batch: ${loadedCount} - ${loadedCount + BATCH_SIZE}`);

    // Parallel Request: Sabhi categories ka data ek saath mangwao fast loading ke liye
    const promises = batch.map(cat => renderSingleShelf(cat));
    const results = await Promise.all(promises);

    // Count successful loads (Kitne shelves actually bane?)
   

    // Check End of List
    const shelvesCreated = results.filter(r => r === true).length;

    loadedCount += batch.length;
    isLoadingShelves = false;

    // Check End of List
    if (loadedCount >= parentCategories.length) {
        if (loader) {
            loader.innerHTML = '<div class="text-center py-4 text-muted"><i class="fas fa-check-circle"></i> You have reached the end!</div>';
            if (shelfObserver) shelfObserver.disconnect();
        }
    } 
    // [FIX] Prevent infinite loop on API errors
    else if (shelvesCreated === 0) {
        console.log("Batch empty or error. Stopping auto-retry to prevent loop.");
        
        // Loop rok dein aur user ko "Try Again" ka button dikhayein
        // Taaki automatic spam na ho
        let loader = document.getElementById('shelves-loader');
        if (loader) {
            loader.innerHTML = `
                <div class="text-center py-4">
                    <p class="text-muted small">Kuch items load nahi ho paye.</p>
                    <button class="btn btn-sm btn-outline-primary" style="margin-top:5px;" onclick="loadNextBatch()">
                        Try Again
                    </button>
                </div>
            `;
        }
    }
}

async function renderSingleShelf(cat) {
    try {
        // API Call: Specific Category + Limit 15 Items
        const url = `/catalog/skus/?category__slug=${cat.slug}&page_size=${PRODUCTS_PER_SHELF}`;
        const prodResponse = await apiCall(url, 'GET', null, false);
        const products = prodResponse.results || prodResponse;

        // Agar products nahi hain, toh shelf mat banao
        if (products.length === 0) return false;

        const shelfHtml = `
            <section class="category-section" style="animation: fadeIn 0.5s ease-in;">
                <div class="section-header">
                    <h3>${cat.name}</h3>
                    <a href="/search_results.html?slug=${cat.slug}" class="view-all-btn">See All <i class="fas fa-chevron-right"></i></a>
                </div>
                <div class="product-scroll-wrapper">
                    ${products.map(p => `
                        <div class="prod-card">
                            <a href="/product.html?code=${p.sku_code}">
                                <div class="prod-img-box">
                                    <img src="${p.image_url || 'https://cdn-icons-png.flaticon.com/512/1147/1147805.png'}" loading="lazy" alt="${p.name}">
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
                            <span>View All</span>
                         </a>
                    </div>
                </div>
            </section>
        `;
        
        // HTML Inject karein (Loader ke just upar)
        const loader = document.getElementById('shelves-loader');
        if (loader) {
            loader.insertAdjacentHTML('beforebegin', shelfHtml);
        }
        return true; 

    } catch (e) {
        console.warn(`Shelf failed for ${cat.name}`, e);
        return false;
    }
}

function setupObserver() {
    const loader = document.getElementById('shelves-loader');
    if (!loader) return;

    const options = {
        root: null, 
        rootMargin: '300px', // Screen bottom se 300px pehle load trigger kar do
        threshold: 0.1 
    };

    shelfObserver = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
            loadNextBatch();
        }
    }, options);

    shelfObserver.observe(loader);
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
    const origBg = btn.style.background;

    btn.innerText = "..";
    btn.disabled = true;

    try {
        await apiCall('/orders/cart/add/', 'POST', { sku_id: skuId, quantity: 1 });

        btn.innerText = "✔";
        btn.style.background = "#32CD32";
        btn.style.color = "#fff";

        if (window.updateGlobalCartCount) window.updateGlobalCartCount();

        setTimeout(() => {
            btn.innerText = "ADD";
            btn.style.background = origBg || "#e6f7ef";
            btn.style.color = "#32CD32";
            btn.disabled = false;
        }, 1500);

    } catch (e) {
        alert(e.message || "Failed");
        btn.innerText = "ADD";
        btn.disabled = false;
    }

}
