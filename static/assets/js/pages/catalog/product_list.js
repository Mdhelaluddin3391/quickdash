// static/assets/js/pages/catalog/product_list.js

// --- Global State for Infinite Scroll ---
let nextPageUrl = null;
let isLoadingProducts = false;
let productObserver;

document.addEventListener('DOMContentLoaded', async () => {
    const grid = document.getElementById('product-grid');
    const titleEl = document.getElementById('page-title');
    
    // Parse URL parameters
    const params = new URLSearchParams(window.location.search);
    const categorySlug = params.get('slug'); 
    const searchQuery = params.get('q');

    // Base API URL
    let apiUrl = '/catalog/skus/';
    let title = 'All Products';

    // --- 1. Determine Context (Category vs Search) ---
    
    if (categorySlug) {
        // Context: Category Page
        try {
            const catResponse = await apiCall(`/catalog/categories/${categorySlug}/`, 'GET', null, false);
            title = catResponse.name;
            
            // Render Subcategory Chips (if any)
            if (catResponse.subcategories && catResponse.subcategories.length > 0) {
                renderSubcategoryChips(catResponse.name, catResponse.subcategories);
            }
        } catch (e) {
            console.warn("Category info fetch failed");
            title = categorySlug.replace(/-/g, ' ').toUpperCase();
        }
        apiUrl += `?category__slug=${categorySlug}`;

    } else if (searchQuery) {
        // Context: Search Results (or Brand via search)
        apiUrl += `?search=${encodeURIComponent(searchQuery)}`;
        title = `Search: "${searchQuery}"`;
    }

    // Set Page Title
    if(titleEl) titleEl.innerText = title;

    // --- 2. Initial Load with Infinite Scroll Support ---
    await loadProducts(apiUrl, true);
});

// Helper: Render Chips
function renderSubcategoryChips(parentName, subcategories) {
    const filterContainer = document.getElementById('brand-filters');
    if (!filterContainer) return;

    filterContainer.innerHTML = ''; 
    
    // "All" Chip
    const allChip = document.createElement('div');
    allChip.className = 'chip active';
    allChip.innerText = `All ${parentName}`;
    filterContainer.appendChild(allChip);

    // Subcategory Chips
    subcategories.forEach(sub => {
        const chip = document.createElement('div');
        chip.className = 'chip';
        chip.innerText = sub.name;
        chip.onclick = () => { window.location.href = `/search_results.html?slug=${sub.slug}`; };
        filterContainer.appendChild(chip);
    });
}

// --- 3. Core Lazy Load Function ---
async function loadProducts(url, isInitial = false) {
    if (isLoadingProducts || !url) return;
    isLoadingProducts = true;

    const grid = document.getElementById('product-grid');
    const emptyState = document.getElementById('empty-state');
    
    // Create/Locate Loader
    let loader = document.getElementById('product-loader');
    if (!loader && grid) {
        loader = document.createElement('div');
        loader.id = 'product-loader';
        loader.className = 'col-12 text-center py-4';
        loader.innerHTML = '<div class="loader">Loading items...</div>';
        grid.after(loader);
    }

    try {
        const response = await apiCall(url, 'GET', null, false); 
        const products = response.results || response; 
        
        // Update Next Page URL for Observer
        nextPageUrl = response.next; 

        if (loader) loader.remove(); 

        // Handle Empty States
        if (isInitial) {
            if (grid) grid.innerHTML = '';
            if (products.length === 0 && emptyState) {
                emptyState.style.display = 'block';
                return;
            } else if (emptyState) {
                emptyState.style.display = 'none';
            }
        }

        renderProducts(products);

        // Setup Observer for Next Page
        if (nextPageUrl) {
            setupProductObserver();
        } else {
            // End of list
            if (productObserver) productObserver.disconnect();
            const endMsg = document.createElement('div');
            endMsg.className = "text-center text-muted col-12 py-3";
            endMsg.innerText = "You've reached the end.";
            if(grid) grid.after(endMsg);
        }

    } catch (error) {
        console.error("Failed to load products", error);
        if (loader) loader.innerHTML = `<p style="color:red;">Failed to load items. <button onclick="loadProducts('${url}')">Retry</button></p>`;
    } finally {
        isLoadingProducts = false;
    }
}

function renderProducts(products) {
    const grid = document.getElementById('product-grid');
    if (!grid) return;

    products.forEach(p => {
        const card = document.createElement('div');
        card.className = 'prod-card';
        card.style.animation = "fadeIn 0.5s ease-in"; 
        
        const price = parseFloat(p.sale_price).toFixed(0);
        const imgUrl = p.image_url || 'https://cdn-icons-png.flaticon.com/512/1147/1147805.png';

        card.innerHTML = `
            <div class="prod-img-box">
                ${p.is_featured ? '<span class="prod-badge">HOT</span>' : ''}
                <img src="${imgUrl}" class="prod-img" alt="${p.name}">
            </div>
            <div class="prod-title">${p.name}</div>
            <div class="prod-unit">${p.unit}</div>
            <div class="prod-footer">
                <div class="prod-price">₹${price}</div>
                <button class="prod-add-btn" onclick="addToCart('${p.id}', this)">ADD</button>
            </div>
            <a href="/product.html?code=${p.sku_code}" style="position:absolute; inset:0; z-index:1;"></a>
        `;
        
        const btn = card.querySelector('.prod-add-btn');
        btn.style.position = 'relative';
        btn.style.zIndex = '2';

        grid.appendChild(card);
    });
}

// --- 4. Intersection Observer (Infinite Scroll) ---
function setupProductObserver() {
    let sentinel = document.getElementById('scroll-sentinel');
    if (!sentinel) {
        sentinel = document.createElement('div');
        sentinel.id = 'scroll-sentinel';
        sentinel.style.height = '10px';
        sentinel.style.width = '100%';
        const grid = document.getElementById('product-grid');
        if (grid) grid.after(sentinel);
    }

    if (productObserver) productObserver.disconnect();

    const options = { root: null, rootMargin: '300px', threshold: 0.1 };

    productObserver = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && nextPageUrl && !isLoadingProducts) {
            loadProducts(nextPageUrl, false);
        }
    }, options);

    productObserver.observe(sentinel);
}

// --- 5. Cart Logic (Auth Required) ---
async function addToCart(skuId, btn) {
    if (!localStorage.getItem('access_token')) {
        window.location.href = '/auth.html';
        return;
    }

    let origText = btn.innerText;
    btn.innerText = "..";
    btn.disabled = true;

    try {
        await apiCall('/orders/cart/add/', 'POST', { sku_id: skuId, quantity: 1 });
        
        btn.innerText = "✔";
        btn.style.backgroundColor = "#32CD32"; 
        btn.style.color = "#fff";
        
        if(window.updateGlobalCartCount) window.updateGlobalCartCount();

        setTimeout(() => {
            btn.innerText = "ADD";
            btn.disabled = false;
            btn.style.backgroundColor = ""; 
            btn.style.color = "";
        }, 1500);

    } catch (e) {
        console.error(e.message || "Failed to add");
        btn.innerText = origText;
        btn.disabled = false;
    }
}