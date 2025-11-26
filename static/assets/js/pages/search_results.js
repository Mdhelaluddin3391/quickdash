document.addEventListener('DOMContentLoaded', () => {
    // 1. URL se search query (e.g., ?q=milk) nikaalein
    const urlParams = new URLSearchParams(window.location.search);
    const query = urlParams.get('q');

    // 2. Query ko page par display karein
    const searchTermEl = document.getElementById('search-term');
    const searchInputEl = document.getElementById('search-input');
    
    if (query) {
        if(searchTermEl) searchTermEl.innerText = query;
        if(searchInputEl) searchInputEl.value = query;
        document.title = `Search for '${query}' - QuickDash`;
    } else {
        if(searchTermEl) searchTermEl.innerText = "all items";
    }

    // Note: Data fetching logic is handled via utils/api.js calling
    // We will move the main logic here as it's page specific.
    
    const grid = document.getElementById('product-grid-container');
    const resultCount = document.getElementById('result-count');
    const noResults = document.getElementById('no-results-message');

    if (query && grid) {
        fetchProducts(query);
    } else if(grid) {
        // Show empty state or all products
        resultCount.innerText = "Please enter a search term";
    }

    async function fetchProducts(searchQuery) {
        try {
            // API call
            // Ensure apiCall is available (api.js included before this)
            const products = await apiCall(`/catalog/skus/?search=${encodeURIComponent(searchQuery)}`);
            
            populateProducts(products);
        } catch (e) {
            console.error("Search failed", e);
            if(resultCount) resultCount.innerText = "Error loading results";
        }
    }

    function populateProducts(products) {
        grid.innerHTML = ''; // Clear old

        if (!products || products.length === 0) {
            resultCount.innerText = "Found 0 items";
            noResults.style.display = 'block';
        } else {
            resultCount.innerText = `Found ${products.length} items`;
            noResults.style.display = 'none';

            products.forEach(product => {
                const productCard = createProductCard(product);
                grid.appendChild(productCard);
            });
        }
    }

    function createProductCard(product) {
        const productEl = document.createElement('div');
        productEl.className = 'product';

        // Image handling
        const imgUrl = product.image_url || 'https://via.placeholder.com/150/E0F7FA/00796B?text=No+Image';
        
        // Button handling
        const buttonHtml = `<button class="add-btn" onclick="window.addToCart('${product.id}')">ADD</button>`;

        productEl.innerHTML = `
            <a href="product.html?code=${product.sku_code}">
                <img src="${imgUrl}" alt="${product.name}">
            </a>
            <h4>${product.name}</h4>
            <p>${product.unit}</p>
            <div class="price">
                <div><span>₹${product.sale_price}</span></div>
                ${buttonHtml}
            </div>
        `;
        return productEl;
    }
    
    // Helper for Add to Cart (Global wrapper)
    window.addToCart = async function(skuId) {
        if (typeof apiCall === 'undefined') return; // Safety check
        
        if (!localStorage.getItem('accessToken')) {
            window.location.href = 'auth.html';
            return;
        }
        try {
            await apiCall('/orders/cart/add/', 'POST', { sku_id: skuId, quantity: 1 }, true);
            alert("Added to cart!");
            // Optional: Update global cart count if function exists
            if(typeof updateGlobalCartCount === 'function') updateGlobalCartCount();
        } catch (e) {
            alert(e.message);
        }
    };
});