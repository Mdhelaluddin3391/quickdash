// static/assets/js/pages/catalog/category_list.js

// --- Global State for Category List ---
let nextCatUrl = '/catalog/categories/?page_size=20'; // Load 20 at a time
let isLoadingCats = false;
let catObserver;

document.addEventListener('DOMContentLoaded', async () => {
    // Initial Load
    await loadCategories(nextCatUrl, true);
});

async function loadCategories(url, isInitial = false) {
    if (isLoadingCats || !url) return;
    isLoadingCats = true;

    const grid = document.getElementById('category-grid');
    
    // Manage Loader
    let loader = document.getElementById('cat-loader');
    if (!loader && grid) {
        loader = document.createElement('div');
        loader.id = 'cat-loader';
        loader.className = 'col-12 text-center py-4';
        loader.innerHTML = '<div class="loader">Loading categories...</div>';
        grid.after(loader);
    }

    try {
        const response = await apiCall(url, 'GET', null, false);
        const categories = response.results || response;
        nextCatUrl = response.next; // Capture next page

        if (loader) loader.remove();

        if (isInitial && grid) {
            grid.innerHTML = '';
            if (categories.length === 0) {
                grid.innerHTML = '<p class="text-muted text-center col-12">No categories found.</p>';
                return;
            }
        }

        renderCategories(categories);

        // Setup Observer
        if (nextCatUrl) {
            setupCatObserver();
        } else {
            if (catObserver) catObserver.disconnect();
        }

    } catch (e) {
        console.error("Category Load Error:", e);
        if (loader) loader.innerHTML = `<p class="error-msg">Failed to load. <button onclick="loadCategories('${url}')">Retry</button></p>`;
    } finally {
        isLoadingCats = false;
    }
}

function renderCategories(categories) {
    const grid = document.getElementById('category-grid');
    if (!grid) return;

    categories.forEach(cat => {
        // Only show Parent categories
        if (!cat.parent) {
            const card = document.createElement('a');
            card.href = `/search_results.html?slug=${cat.slug}`;
            card.className = 'cat-card';
            // Smooth fade-in animation
            card.style.animation = "fadeIn 0.5s ease-in";
            
            const icon = cat.icon_url || 'https://cdn-icons-png.flaticon.com/512/2921/2921822.png';

            card.innerHTML = `
                <img src="${icon}" alt="${cat.name}" class="cat-img">
                <div class="cat-name">${cat.name}</div>
            `;
            grid.appendChild(card);
        }
    });
}

function setupCatObserver() {
    let sentinel = document.getElementById('cat-sentinel');
    if (!sentinel) {
        sentinel = document.createElement('div');
        sentinel.id = 'cat-sentinel';
        sentinel.style.height = '10px';
        sentinel.style.width = '100%';
        const grid = document.getElementById('category-grid');
        if (grid) grid.after(sentinel);
    }

    if (catObserver) catObserver.disconnect();

    const options = { root: null, rootMargin: '200px', threshold: 0.1 };

    catObserver = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && nextCatUrl && !isLoadingCats) {
            loadCategories(nextCatUrl, false);
        }
    }, options);

    catObserver.observe(sentinel);
}