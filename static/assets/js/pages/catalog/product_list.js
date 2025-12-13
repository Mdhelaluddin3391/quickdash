// static/assets/js/pages/catalog/product_list.js
let nextPageUrl = null;
let isLoadingProducts = false;
let productObserver;



document.addEventListener('DOMContentLoaded', async () => {
    const grid = document.getElementById('product-grid');
    const titleEl = document.getElementById('page-title');
    
    const params = new URLSearchParams(window.location.search);
    const categorySlug = params.get('slug'); 
    const searchQuery = params.get('q');

    let apiUrl = '/catalog/skus/';
    let title = 'All Products';

    // --- Logic Start ---
    
    if (categorySlug) {
        // Case A: Category Filter
        try {
            const catResponse = await apiCall(`/catalog/categories/${categorySlug}/`, 'GET', null, false);
            title = catResponse.name;
            
            // Subcategory Chips Logic (Unchanged)
            if (catResponse.subcategories && catResponse.subcategories.length > 0) {
                const filterContainer = document.getElementById('brand-filters');
                if (filterContainer) {
                    filterContainer.innerHTML = ''; 
                    const allChip = document.createElement('div');
                    allChip.className = 'chip active';
                    allChip.innerText = `All ${catResponse.name}`;
                    filterContainer.appendChild(allChip);
                    catResponse.subcategories.forEach(sub => {
                        const chip = document.createElement('div');
                        chip.className = 'chip';
                        chip.innerText = sub.name;
                        chip.onclick = () => { window.location.href = `/search_results.html?slug=${sub.slug}`; };
                        filterContainer.appendChild(chip);
                    });
                }
            }
        } catch (e) {
            console.warn("Category info fetch failed");
            title = categorySlug.replace(/-/g, ' ').toUpperCase();
        }
        apiUrl += `?category__slug=${categorySlug}`;
    } else if (searchQuery) {
        apiUrl += `?search=${encodeURIComponent(searchQuery)}`;
        title = `Search: "${searchQuery}"`;
    }

    if(titleEl) titleEl.innerText = title;

    // Initial Load
    await loadProducts(apiUrl, true); // true = Initial reset
});


async function loadProducts(url, isInitial = false) {
    if (isLoadingProducts || !url) return;
    isLoadingProducts = true;

    const grid = document.getElementById('product-grid');
    const emptyState = document.getElementById('empty-state');
    
    // Add Loader at bottom if not initial
    let loader = document.getElementById('product-loader');
    if (!loader && grid) {
        loader = document.createElement('div');
        loader.id = 'product-loader';
        loader.className = 'col-12 text-center py-4';
        loader.innerHTML = '<div class="loader"></div>';
        grid.after(loader);
    }

    try {
        const response = await apiCall(url, 'GET', null, false); 
        const products = response.results || response; 
        
        // Capture Next Page URL for Infinite Scroll
        nextPageUrl = response.next; 

        if (loader) loader.remove(); // Remove loader after fetch

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
        } else if (productObserver) {
            productObserver.disconnect();
        }

    } catch (error) {
        console.error("Failed to load products", error);
        if (loader) loader.innerHTML = `<p style="color:red;">Error loading items.</p>`;
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
        card.style.animation = "fadeIn 0.5s ease-in"; // Smooth entry
        
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


function setupProductObserver() {
    // Create a sentinel element at the bottom
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

    const options = { root: null, rootMargin: '200px', threshold: 0.1 };

    productObserver = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && nextPageUrl) {
            loadProducts(nextPageUrl, false);
        }
    }, options);

    productObserver.observe(sentinel);
}

// Cart Logic (Auth Required here)
async function addToCart(skuId, btn) {
    // FIX: Correct key 'access_token' used here
    if (!localStorage.getItem('access_token')) {
        window.location.href = '/auth.html';
        return;
    }

    // UX: Button Loading State
    let origText = "ADD";
    if (btn) {
        origText = btn.innerText;
        btn.innerText = "..";
        btn.disabled = true;
    }

    try {
        await apiCall('/orders/cart/add/', 'POST', { sku_id: skuId, quantity: 1 });
        
        // Success Feedback
        if (btn) {
            btn.innerText = "✔";
            btn.style.backgroundColor = "#32CD32"; // Green
            btn.style.color = "#fff";
        }
        
        // Toast Notification (agar toast.js hai toh)
        if (window.showSuccess) showSuccess('Item added to cart!', 2000);
        
        // Update cart count badge
        if(window.updateGlobalCartCount) window.updateGlobalCartCount();

        // Reset Button
        setTimeout(() => {
            if (btn) {
                btn.innerText = "ADD";
                btn.disabled = false;
                btn.style.backgroundColor = ""; // Reset to CSS default
                btn.style.color = "";
            }
        }, 1500);

    } catch (e) {
        if (window.showError) showError(e.message || "Failed to add item", 3000);
        console.error(e.message || "Failed to add");
        
        // Reset Button on Error
        if (btn) {
            btn.innerText = origText;
            btn.disabled = false;
        }
    }
}