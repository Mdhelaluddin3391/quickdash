// static/assets/js/utils/home.js

// --- Global Variables for Infinite Scroll ---
let parentCategories = []; 
let loadedCount = 0;       
const BATCH_SIZE = 2;      // 2 Categories ek saath load karenge
let isLoadingShelves = false; 
let shelfObserver;        // Observer ko global scope mein rakhein

document.addEventListener('DOMContentLoaded', async () => {
    console.log("Loading initial data...");

    await loadBanners();
    await loadHomeCategories();
    await loadFlashSales();
    await loadBrands();
    initProductShelves();
    
    console.log("All initial data loading initiated.");
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
// 5. SMART SHELVES (Fixed Logic)
// =========================================================

async function initProductShelves() {
    const container = document.getElementById('dynamic-sections-container');
    if (!container) return;
    
    // Loader dikhayein
    container.innerHTML = '<div id="shelves-loader" class="text-center py-4" style="clear:both; width:100%;"><div class="loader">Loading shelves...</div></div>';

    try {
        // 1. Backend se saari Categories mangwayein
        // requireAuth = false rakha hai taaki bina login ke bhi dikhe
        const catResponse = await apiCall('/catalog/categories/?page_size=100', 'GET', null, false);
        const allCats = catResponse.results || catResponse;
        
        // Sirf Parent Categories filter karein (Top level)
        parentCategories = allCats.filter(c => !c.parent);

        console.log(`Found ${parentCategories.length} parent categories.`);

        if (parentCategories.length === 0) {
            container.innerHTML = '<p class="text-center text-muted py-4">No categories found.</p>';
            return;
        }
        
        // 2. Loading Shuru Karein
        await loadNextBatch();

        // 3. Scroll Observer lagayein
        setupObserver();

    } catch (e) {
        console.error("Shelves Init Error:", e);
        // Error user ko dikhayein par console main detail dekhein
        container.innerHTML = '<p class="text-danger text-center py-4">Failed to load shelves. Please check console.</p>';
    }
}

async function loadNextBatch() {
    // Agar loading chal rahi hai ya list khatam, toh ruk jao
    if (isLoadingShelves || loadedCount >= parentCategories.length) return;
    
    isLoadingShelves = true;
    
    // Loader ensure karein
    let loader = document.getElementById('shelves-loader');
    if (!loader) {
        const container = document.getElementById('dynamic-sections-container');
        container.insertAdjacentHTML('beforeend', '<div id="shelves-loader" class="text-center py-4"><div class="loader">Loading...</div></div>');
        loader = document.getElementById('shelves-loader');
    }
    loader.style.display = 'block';

    // Batch banayein
    const batch = parentCategories.slice(loadedCount, loadedCount + BATCH_SIZE);
    let itemsAddedInThisBatch = 0;

    console.log(`Loading batch: ${loadedCount} to ${loadedCount + BATCH_SIZE}`);

    // Har category ke liye API call karein
    for (const cat of batch) {
        const added = await renderSingleShelf(cat);
        if (added) itemsAddedInThisBatch++;
    }

    loadedCount += batch.length;
    isLoadingShelves = false;

    // [MAGIC FIX]: Agar batch load hua lekin screen par kuch nahi aaya (Categories empty thi),
    // toh user scroll nahi kar payega. Isliye hum TURANT agla batch call karte hain.
    if (itemsAddedInThisBatch === 0 && loadedCount < parentCategories.length) {
        console.log("Empty batch detected, automatically loading next...");
        loadNextBatch(); 
    }

    // Agar sab khatam ho gaya to loader hata do
    if (loadedCount >= parentCategories.length) {
        if (loader) loader.remove();
        if (shelfObserver) shelfObserver.disconnect();
    }
}

async function renderSingleShelf(cat) {
    try {
        // API call: Category Slug bhejein
        // page_size=20 (Jaisa aapne manga tha)
        const prodResponse = await apiCall(`/catalog/skus/?category__slug=${cat.slug}&page_size=20`, 'GET', null, false);
        const products = prodResponse.results || prodResponse;

        if (products.length > 0) {
            const shelfHtml = `
                <section class="category-section" style="animation: fadeIn 0.5s ease-in;">
                    <div class="section-header">
                        <h3>${cat.name}</h3>
                        <a href="/search_results.html?slug=${cat.slug}" class="view-all-btn">See All</a>
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
                             </a>
                        </div>
                    </div>
                </section>
            `;
            
            // HTML Inject karein (Loader ke just pehle)
            const loader = document.getElementById('shelves-loader');
            if (loader) {
                loader.insertAdjacentHTML('beforebegin', shelfHtml);
            }
            return true; // Success: Shelf bani
        }
    } catch (e) {
        console.warn(`Shelf load failed for ${cat.name}`, e);
    }
    return false; // Fail: Shelf nahi bani
}

function setupObserver() {
    const loader = document.getElementById('shelves-loader');
    if (!loader) return;

    const options = {
        root: null, 
        rootMargin: '200px', // Screen bottom se 200px pehle load trigger karo
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