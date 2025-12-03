// static/assets/js/utils/home.js

document.addEventListener('DOMContentLoaded', async () => {
    // Saare APIs ko parallel main call karenge taaki page fast load ho
    await Promise.all([
        loadBanners(),
        loadHomeCategories(),
        loadFlashSales(),
        loadBrands(),
        loadProductShelves()
    ]);
});

// --- 1. Hero Banners Load Karo ---
async function loadBanners() {
    const slider = document.getElementById('hero-slider');
    if (!slider) return;

    try {
        const response = await apiCall('/catalog/banners/', 'GET', null, false);
        const banners = response.results || response;
        
        // Sirf 'HERO' position wale banners filter karo
        const heroBanners = banners.filter(b => b.position === 'HERO');
        
        if (heroBanners.length > 0) {
            slider.innerHTML = heroBanners.map(b => `
                <a href="${b.target_url}" class="promo-card" style="background: ${b.bg_gradient}">
                    <div class="promo-content">
                        <h2>${b.title}</h2>
                        <p>Click to Explore</p>
                        <span class="promo-btn" style="background:#fff; color:#333; padding:5px 12px; border-radius:20px; font-weight:700; font-size:0.8rem; margin-top:10px; display:inline-block;">Shop Now</span>
                    </div>
                    <img src="${b.image_url}" class="promo-img" alt="${b.title}">
                </a>
            `).join('');
        } else {
            // Agar API khali hai toh Default Banner dikhao
            slider.innerHTML = `<div class="promo-card" style="background: linear-gradient(135deg, #32CD32, #2ecc71);">
                <div class="promo-content"><h2>Welcome to<br>QuickDash</h2></div>
            </div>`;
        }
    } catch (e) {
        console.error("Banner Error:", e);
    }
}

// --- 2. Categories Load Karo ---
async function loadHomeCategories() {
    const grid = document.getElementById('home-category-grid');
    if (!grid) return;
    
    try {
        // Top 8 categories mangwao
        const response = await apiCall('/catalog/categories/?page_size=8', 'GET', null, false);
        const cats = response.results || response;
        const parents = cats.filter(c => !c.parent);

        grid.innerHTML = parents.map(c => `
            <div class="cat-item-home" onclick="window.location.href='/search_results.html?slug=${c.slug}'">
                <div class="cat-icon-box">
                    <img src="${c.icon_url || 'https://cdn-icons-png.flaticon.com/512/2921/2921822.png'}" alt="${c.name}">
                </div>
                <span class="cat-label" style="font-size:0.75rem; font-weight:600;">${c.name}</span>
            </div>
        `).join('');

    } catch (e) {
        grid.innerHTML = '<p class="text-danger text-center">Failed to load</p>';
    }
}


async function loadBanners() {
    const slider = document.getElementById('hero-slider');
    const midContainer = document.getElementById('mid-banner-container');

    try {
        const response = await apiCall('/catalog/banners/', 'GET', null, false);
        const banners = response.results || response;
        
        // A. Process Hero Sliders
        const heroBanners = banners.filter(b => b.position === 'HERO');
        if (slider) {
            if (heroBanners.length > 0) {
                slider.innerHTML = heroBanners.map(b => `
                    <a href="${b.target_url}" class="promo-card" style="background: ${b.bg_gradient}">
                        <div class="promo-content">
                            <h2>${b.title}</h2>
                            <p>Click to Explore</p>
                            <span class="promo-btn" style="background:#fff; color:#333; padding:5px 12px; border-radius:20px; font-weight:700; font-size:0.8rem; margin-top:10px; display:inline-block;">Shop Now</span>
                        </div>
                        <img src="${b.image_url}" class="promo-img" alt="${b.title}" loading="lazy">
                    </a>
                `).join('');
            } else {
                // Default
                slider.innerHTML = `<div class="promo-card" style="background: linear-gradient(135deg, #32CD32, #2ecc71);">
                    <div class="promo-content"><h2>Welcome to<br>QuickDash</h2></div>
                </div>`;
            }
        }

        // B. Process Mid Banner (Take the first active MID banner)
        const midBanners = banners.filter(b => b.position === 'MID');
        if (midContainer && midBanners.length > 0) {
            const mid = midBanners[0]; // Sirf ek dikhana hai
            midContainer.style.display = 'block';
            midContainer.innerHTML = `
                <a href="${mid.target_url}">
                    <img src="${mid.image_url}" alt="${mid.title}" loading="lazy" style="width:100%; border-radius:12px; box-shadow:0 4px 10px rgba(0,0,0,0.1);">
                </a>
            `;
        } else if (midContainer) {
            midContainer.style.display = 'none'; // Hide if no data
        }

    } catch (e) {
        console.error("Banner Error:", e);
    }
}

// --- 3. Flash Sales (Deal of the Day) ---
async function loadFlashSales() {
    const container = document.getElementById('flash-sale-section');
    const grid = document.getElementById('flash-sale-grid');
    if (!container || !grid) return;
    
    try {
        const response = await apiCall('/catalog/flash-sales/', 'GET', null, false);
        const sales = response.results || response;

        if (sales.length === 0) {
            container.style.display = 'none'; // Agar koi sale nahi hai toh section chhupa do
            return;
        }

        container.style.display = 'block';
        
        // Timer shuru karo (Pehle item ki end_time ke hisaab se)
        if (sales[0] && sales[0].end_time) {
            startTimer(new Date(sales[0].end_time));
        }

        grid.innerHTML = sales.map(sale => `
            <div class="flash-card" style="flex:0 0 150px; background:#fff; padding:10px; border-radius:12px; position:relative; border:1px solid #eee;">
                <div class="badge-off" style="position:absolute; top:0; left:0; background:#ff6b6b; color:#fff; font-size:0.65rem; padding:2px 6px; border-radius:10px 0 10px 0; z-index:2;">
                    ${sale.discount_percent}% OFF
                </div>
                <img src="${sale.sku_image || 'https://cdn-icons-png.flaticon.com/512/2553/2553691.png'}" style="width:70px; height:70px; object-fit:contain; margin:15px auto 10px; display:block;">
                <div class="f-info">
                    <div style="font-size:0.85rem; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${sale.sku_name}</div>
                    <div class="price">
                        <span style="font-weight:800;">₹${parseFloat(sale.discounted_price).toFixed(0)}</span>
                        <span style="text-decoration:line-through; color:#b2bec3; font-size:0.75rem; margin-left:5px;">₹${parseFloat(sale.original_price).toFixed(0)}</span>
                    </div>
                    <div class="flash-action-row" style="display:flex; justify-content:space-between; align-items:flex-end; margin-top:8px;">
                        <div class="progress-wrapper" style="flex-grow:1; margin-right:8px;">
                            <div class="progress-bar" style="height:5px; background:#eee; border-radius:3px; overflow:hidden;">
                                <div style="width:${sale.percentage_sold}%; height:100%; background:#e67e22;"></div>
                            </div>
                            <small style="font-size:0.65rem; color:#e67e22;">${sale.percentage_sold}% Sold</small>
                        </div>
                        <button onclick="addToCart('${sale.sku_id}', this)" style="padding:4px 12px; background:#fff; border:1px solid #32CD32; color:#32CD32; border-radius:6px; font-weight:700; font-size:0.75rem; cursor:pointer;">ADD</button>
                    </div>
                </div>
            </div>
        `).join('');

    } catch (e) {
        console.error("Flash Sale Error", e);
        container.style.display = 'none';
    }
}

// Timer Logic
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

        display.innerHTML = `Ends in <span class="time-box" style="background:#d35400; color:#fff; padding:2px 5px; border-radius:4px;">${h}h : ${m}m : ${s}s</span>`;
    }, 1000);
}

// --- 4. Brands Load Karo ---
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

// --- 5. Product Shelves Load Karo (Best Sellers etc.) ---
async function loadProductShelves() {
    const container = document.getElementById('dynamic-sections-container');
    if (!container) return;
    
    container.innerHTML = ''; 

    // Pehle top 5 categories layenge
    const catResponse = await apiCall('/catalog/categories/', 'GET', null, false);
    const cats = (catResponse.results || catResponse).slice(0, 5); 

    for (const cat of cats) {
        // Har category ke liye products layenge
        const prodResponse = await apiCall(`/catalog/skus/?category__slug=${cat.slug}&page_size=6`, 'GET', null, false);
        const products = prodResponse.results || prodResponse;

        if (products.length > 0) {
            const shelfHtml = `
                <section class="category-section" style="background:#fff; margin-bottom:15px; border-top:1px solid #f0f0f0;">
                    <div class="section-header" style="display:flex; justify-content:space-between; padding:20px 20px 10px;">
                        <h3 style="font-size:1.1rem; font-weight:700;">${cat.name}</h3>
                        <a href="/search_results.html?slug=${cat.slug}" class="view-all-btn" style="color:var(--primary); font-weight:600;">See All</a>
                    </div>
                    <div class="product-scroll-wrapper" style="overflow-x:auto; padding:10px 20px 30px; display:flex; gap:15px; scrollbar-width:none;">
                        ${products.map(p => `
                            <div class="prod-card" style="flex:0 0 160px; background:#fff; border:1px solid #dfe6e9; border-radius:12px; padding:12px; display:flex; flex-direction:column; justify-content:space-between;">
                                <a href="/product.html?code=${p.sku_code}" style="text-decoration:none; color:inherit;">
                                    <div class="prod-img-box" style="height:100px; display:flex; align-items:center; justify-content:center; margin-bottom:10px;">
                                        <img src="${p.image_url || 'https://cdn-icons-png.flaticon.com/512/1147/1147805.png'}" style="max-height:100%; max-width:100%; object-fit:contain;">
                                    </div>
                                    <div class="prod-title" style="font-size:0.9rem; font-weight:600; margin-bottom:4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${p.name}</div>
                                    <div class="prod-unit" style="font-size:0.75rem; color:#636e72;">${p.unit}</div>
                                </a>
                                <div class="prod-footer" style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">
                                    <div class="prod-price" style="font-weight:700;">₹${parseFloat(p.sale_price).toFixed(0)}</div>
                                    <button onclick="addToCart('${p.id}', this)" style="padding:5px 12px; background:#e6f7ef; border:1px solid #32CD32; color:#32CD32; border-radius:6px; font-weight:700; font-size:0.75rem; cursor:pointer;">ADD</button>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </section>
            `;
            container.innerHTML += shelfHtml;
        }
    }
}

// --- Cart Logic ---
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
        // Navbar cart update karo
        if(window.updateGlobalCartCount) window.updateGlobalCartCount();
    } catch (e) {
        alert(e.message || "Failed");
        btn.innerText = origText;
        btn.disabled = false;
    }
}