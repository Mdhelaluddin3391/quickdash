// static/assets/js/utils/home.js

// --- Global Variables ---
let homeFeedPage = 1;
let isFeedLoading = false;
let hasMoreFeed = true;
let feedObserver;
let cartMap = {}; // Stores sku_id -> quantity mapping

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Inject Custom CSS for Buttons
    injectHomeStyles();

    // 2. Fetch Cart Data First (To show correct quantities)
    // FIX: This must complete before rendering shelves to show correct buttons
    await fetchCartState();

    // 3. Load Static Sections
    // We run these in parallel for speed
    Promise.all([
        loadBanners(),
        loadHomeCategories(),
        loadFlashSales(),
        loadBrands()
    ]);

    // 4. Start Infinite Feed
    initProductShelves();
});

// =========================================================
// 0. HELPER: CSS & CART STATE
// =========================================================
function injectHomeStyles() {
    const style = document.createElement('style');
    style.innerHTML = `
        .btn-add-initial {
            background: #fff;
            border: 1px solid #32CD32;
            color: #32CD32;
            padding: 5px 20px;
            border-radius: 4px;
            font-weight: 700;
            font-size: 0.85rem;
            cursor: pointer;
            width: 80px;
            text-align: center;
            transition: all 0.2s;
        }
        .btn-add-initial:hover {
            background: #32CD32;
            color: #fff;
        }
        .qty-control {
            display: flex;
            align-items: center;
            background: #32CD32;
            border-radius: 4px;
            width: 80px;
            justify-content: space-between;
            padding: 2px 0;
        }
        .qty-btn {
            background: none;
            border: none;
            color: #fff;
            font-weight: bold;
            font-size: 1.1rem;
            width: 25px;
            cursor: pointer;
            padding: 0;
            line-height: 1;
        }
        .qty-val {
            color: #fff;
            font-weight: 600;
            font-size: 0.9rem;
        }
    `;
    document.head.appendChild(style);
}

async function fetchCartState() {
    // If user is not logged in, skip fetching cart
    if (!localStorage.getItem('access_token')) return;

    try {
        // FIX: Changed 'false' to 'true' to enable Authentication
        const response = await apiCall('/orders/cart/', 'GET', null, true);
        
        const cartItems = response.items || [];
        cartMap = {};
        
        // Map SKU IDs to Quantities
        cartItems.forEach(item => {
            // Support both flat structure and nested sku object
            const skuId = item.sku ? item.sku.id : item.sku_id;
            cartMap[skuId] = item.quantity;
        });
        
    } catch (e) {
        // If 401 occurs here (token expired), apiCall will handle redirect.
        // For other errors, we just log warning so homepage still loads.
        console.warn("[Home] Could not sync cart state:", e);
    }
}

// =========================================================
// 1. HERO BANNERS
// =========================================================
async function loadBanners() {
    const slider = document.getElementById('hero-slider');
    const midContainer = document.getElementById('mid-banner-container');
    if (!slider && !midContainer) return;

    try {
        const response = await apiCall('/catalog/banners/', 'GET', null, false);
        const banners = response.results || response;

        // A. Hero Slider
        const heroBanners = banners.filter(b => b.position === 'HERO');
        if (slider) {
            if (heroBanners.length > 0) {
                slider.innerHTML = heroBanners.map(b => `
                <a href="${b.target_url || '#'}" class="promo-card" style="background: ${b.bg_gradient || '#333'}">
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
        if (midContainer) {
            if (midBanners.length > 0) {
                midContainer.style.display = 'block';
                midContainer.innerHTML = `
                <a href="${midBanners[0].target_url || '#'}">
                    <img src="${midBanners[0].image_url}" alt="Offer" loading="lazy" style="width:100%; border-radius:8px;">
                </a>`;
            } else {
                midContainer.style.display = 'none';
            }
        }

    } catch (e) {
        console.warn("[Home] Banner Error:", e);
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
                <img src="${c.icon_url || 'https://cdn-icons-png.flaticon.com/512/2921/2921822.png'}" alt="${c.name}" onerror="this.src='https://cdn-icons-png.flaticon.com/512/2921/2921822.png'">
            </div>
            <span class="cat-label">${c.name}</span>
        </div>
    `).join('');

    } catch (e) {
        console.warn("[Home] Category Error:", e);
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

        grid.innerHTML = sales.map(sale => {
            const qty = cartMap[sale.sku_id] || 0;
            
            let btnHtml;
            if (qty > 0) {
                btnHtml = getQtyControlHtml(sale.sku_id, qty);
            } else {
                btnHtml = `<button onclick="addToCart('${sale.sku_id}', 1, this)" style="width:100%; background:#e67e22; color:white; border:none; padding:6px; border-radius:4px; font-weight:600; cursor:pointer;">ADD</button>`;
            }

            return `
            <div class="flash-card">
                <div class="badge-off">${sale.discount_percent}% OFF</div>
                <img src="${sale.sku_image || 'https://cdn-icons-png.flaticon.com/512/2553/2553691.png'}" onerror="this.src='https://via.placeholder.com/150'">
                <div class="f-info">
                    <div style="height: 40px; overflow: hidden; font-size:0.9rem; margin-bottom:5px;">${sale.sku_name}</div>
                    <div class="price">
                        <span>₹${parseFloat(sale.discounted_price).toFixed(0)}</span>
                        <span style="text-decoration:line-through; font-weight:400; font-size:0.8rem; color:#888;">₹${parseFloat(sale.original_price).toFixed(0)}</span>
                    </div>
                    <div id="action-wrapper-${sale.sku_id}" class="mt-2" style="min-height:36px; display:flex; align-items:center; justify-content:center;">
                        ${btnHtml}
                    </div>
                </div>
            </div>
            `;
        }).join('');

    } catch (e) {
        console.warn("[Home] Flash Sale Error", e);
        container.style.display = 'none';
    }
}

function startTimer(endTime) {
    const display = document.getElementById('flash-timer-display');
    if (!display) return;
    
    // Clear any existing interval to prevent duplicates
    if (window.flashTimerInterval) clearInterval(window.flashTimerInterval);

    window.flashTimerInterval = setInterval(() => {
        const now = new Date();
        const diff = endTime - now;
        if (diff <= 0) {
            display.innerText = "Ended";
            clearInterval(window.flashTimerInterval);
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
            <div class="brand-circle" onclick="window.location.href='/search_results.html?search=${encodeURIComponent(b.name)}'"> 
                <img src="${b.logo_url || 'https://cdn-icons-png.flaticon.com/512/888/888879.png'}" alt="${b.name}"> 
            </div>
        `).join('');
    } catch (e) {
        console.warn("[Home] Brand Error", e);
    }
}

// =========================================================
// 5. INFINITE FEED
// =========================================================

async function initProductShelves() {
    const container = document.getElementById('dynamic-sections-container');
    if (!container) return;

    container.innerHTML = ''; 
    homeFeedPage = 1;
    hasMoreFeed = true;
    
    const loader = document.createElement('div');
    loader.id = 'feed-loader';
    loader.className = 'text-center py-5';
    loader.innerHTML = '<div class="spinner-border text-success" role="status"></div><div class="mt-2 text-muted small">Loading suggestions...</div>';
    container.appendChild(loader);

    setupFeedObserver();
}

async function loadNextFeedBatch() {
    if (isFeedLoading || !hasMoreFeed) return;
    
    isFeedLoading = true;
    const loader = document.getElementById('feed-loader');
    
    try {
        const response = await apiCall(`/catalog/api/home/feed/?page=${homeFeedPage}`, 'GET', null, false);
        
        const sections = response.sections || [];
        hasMoreFeed = response.has_more;
        homeFeedPage = response.next_page;

        sections.forEach(section => {
            renderSection(section);
        });

        if (!hasMoreFeed) {
            if(feedObserver) feedObserver.disconnect();
            if(loader) {
                loader.innerHTML = '';
                renderEndOfPageCTA(loader);
            }
        }

    } catch (error) {
        console.warn("[Home] Feed Load Error:", error);
        if(loader) loader.innerHTML = `<p class="text-center text-muted">That's all for now!</p>`;
    } finally {
        isFeedLoading = false;
    }
}

function renderSection(section) {
    const loader = document.getElementById('feed-loader'); 
    if (!loader) return;

    const html = `
        <section class="category-section" style="animation: fadeIn 0.5s ease-out; margin-bottom: 30px;">
            <div class="section-header d-flex justify-content-between align-items-center px-3 mb-2">
                <h3 style="font-size: 1.1rem; font-weight: 700; margin:0;">${section.category_name}</h3>
                <a href="/search_results.html?slug=${section.category_slug}" class="text-success text-decoration-none small" style="font-weight:600;">
                    See All <i class="fas fa-chevron-right"></i>
                </a>
            </div>
            
            <div class="product-scroll-wrapper d-flex" style="overflow-x: auto; gap: 15px; padding: 10px 15px; scroll-behavior: smooth; -webkit-overflow-scrolling: touch;">
                ${section.products.map(p => {
                    const qty = cartMap[p.id] || 0;
                    const buttonHtml = qty > 0 
                        ? getQtyControlHtml(p.id, qty) 
                        : `<button id="btn-${p.id}" onclick="addToCart('${p.id}', 1, this)" class="btn-add-initial">ADD</button>`;

                    return `
                    <div class="prod-card" style="min-width: 160px; max-width: 160px; background: #fff; border-radius: 12px; padding: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); border:1px solid #f0f0f0;">
                        <a href="/product.html?code=${p.sku_code}" class="text-decoration-none text-dark">
                            <div class="prod-img-box position-relative mb-2" style="height: 120px; display: flex; align-items: center; justify-content: center;">
                                ${p.is_featured ? '<span class="badge bg-danger position-absolute top-0 start-0" style="font-size:0.6rem;">HOT</span>' : ''}
                                <img src="${p.image || 'https://via.placeholder.com/150'}" loading="lazy" style="max-height: 100%; max-width: 100%; object-fit: contain;">
                            </div>
                            <div class="prod-title text-truncate small fw-bold mb-1">${p.name}</div>
                            <div class="prod-unit text-muted small mb-2" style="font-size: 0.75rem;">${p.unit || 'Unit'}</div>
                        </a>
                        <div class="prod-footer d-flex justify-content-between align-items-center">
                            <div class="prod-price fw-bold">₹${p.price.toFixed(0)}</div>
                            <div id="action-wrapper-${p.id}">
                                ${buttonHtml}
                            </div>
                        </div>
                    </div>
                `}).join('')}
                
                <div class="view-all-card d-flex align-items-center justify-content-center" style="min-width: 120px;">
                     <a href="/search_results.html?slug=${section.category_slug}" class="text-center text-success text-decoration-none">
                        <div style="font-size: 2rem; margin-bottom:5px;"><i class="fas fa-arrow-right"></i></div>
                        <small style="font-weight:600;">View All</small>
                     </a>
                </div>
            </div>
        </section>
    `;

    loader.insertAdjacentHTML('beforebegin', html);
}

// --- HTML Generator for Qty Control ---
function getQtyControlHtml(skuId, qty) {
    return `
        <div class="qty-control">
            <button class="qty-btn" onclick="updateCartQty('${skuId}', -1)">-</button>
            <span class="qty-val" id="qty-${skuId}">${qty}</span>
            <button class="qty-btn" onclick="updateCartQty('${skuId}', 1)">+</button>
        </div>
    `;
}

function renderEndOfPageCTA(container) {
    if(!container) return;
    container.innerHTML = `
        <div class="end-page-cta text-center py-4" style="animation: fadeIn 0.5s;">
            <div class="cta-icon-box text-muted mb-2" style="font-size:2rem;"><i class="fas fa-search"></i></div>
            <h5 class="cta-title text-muted">That's all for now!</h5>
            <button class="btn btn-outline-success mt-2" onclick="scrollToSearch()">Search Items</button>
        </div>
    `;
}

function setupFeedObserver() {
    const loader = document.getElementById('feed-loader');
    if (!loader) return;
    
    if (feedObserver) feedObserver.disconnect();
    
    const options = { rootMargin: '200px', threshold: 0.1 };
    feedObserver = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
            loadNextFeedBatch();
        }
    }, options);
    feedObserver.observe(loader);
}

// =========================================================
// 6. CART LOGIC (ADD / UPDATE)
// =========================================================

// Called when clicking "ADD" initially
async function addToCart(skuId, qty, btn) {
    // Auth Check
    if (!localStorage.getItem('access_token')) {
        // Use Global URL Config if available
        const loginUrl = (window.APP_CONFIG && window.APP_CONFIG.URLS) ? window.APP_CONFIG.URLS.LOGIN : '/auth.html';
        window.location.href = loginUrl;
        return;
    }

    // Immediate UI Feedback
    const wrapper = document.getElementById(`action-wrapper-${skuId}`);
    const originalHtml = wrapper ? wrapper.innerHTML : '';
    
    if (wrapper) {
        wrapper.innerHTML = `<div class="spinner-border spinner-border-sm text-success" role="status"></div>`;
    }

    try {
        await apiCall('/orders/cart/add/', 'POST', { sku_id: skuId, quantity: qty });
        
        // Update Local State
        const newQty = (cartMap[skuId] || 0) + qty;
        cartMap[skuId] = newQty;

        // Render Quantity Control
        if (wrapper) wrapper.innerHTML = getQtyControlHtml(skuId, newQty);
        
        // Refresh Global Cart Count (in Navbar)
        if (window.updateGlobalCartCount) window.updateGlobalCartCount();
        
        // Show Toast
        if(window.showToast) showToast("Item added to cart", "success");

    } catch (e) {
        console.error("Failed to add:", e);
        if(window.showToast) showToast(e.message || "Could not add item", "error");
        else alert("Failed to add item");
        
        // Revert UI
        if (wrapper) wrapper.innerHTML = originalHtml;
    }
}

// Called when clicking + or - in the counter
async function updateCartQty(skuId, change) {
    const currentQty = cartMap[skuId] || 0;
    const newQty = currentQty + change;
    
    const qtySpan = document.getElementById(`qty-${skuId}`);
    const wrapper = document.getElementById(`action-wrapper-${skuId}`);

    // 1. Optimistic UI Update
    if (newQty <= 0) {
        if (wrapper) wrapper.innerHTML = `<button id="btn-${skuId}" onclick="addToCart('${skuId}', 1, this)" class="btn-add-initial">ADD</button>`;
        delete cartMap[skuId];
    } else {
        if (qtySpan) qtySpan.innerText = newQty;
        cartMap[skuId] = newQty;
    }

    // 2. API Call (Background)
    try {
        if (newQty <= 0) {
            await apiCall(`/orders/cart/items/${skuId}/`, 'DELETE');
            if(window.showToast) showToast("Item removed", "info");
        } else {
            // FIX: Sending new total quantity, not change
            await apiCall('/orders/cart/add/', 'POST', { sku_id: skuId, quantity: newQty });
        }
        
        if (window.updateGlobalCartCount) window.updateGlobalCartCount();

    } catch (e) {
        console.error("Cart Update Failed", e);
        if(window.showToast) showToast("Update failed. Refreshing...", "error");
        
        // Revert UI by reloading cart state
        await fetchCartState();
        // Force refresh shelves to fix numbers
        // A full reload is safer here to ensure data consistency
        // window.location.reload(); 
    }
}

// =========================================================
// 7. BOTTOM CTA ACTIONS
// =========================================================

function scrollToSearch() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    setTimeout(() => {
        const searchInput = document.querySelector('input[name="q"]');
        if (searchInput) {
            searchInput.focus();
            searchInput.click(); // For mobile behavior
        }
    }, 800); 
}