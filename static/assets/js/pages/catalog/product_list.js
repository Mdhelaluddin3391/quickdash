// static/assets/js/pages/catalog/product_list.js

document.addEventListener('DOMContentLoaded', async () => {
    const grid = document.getElementById('product-grid');
    const titleEl = document.getElementById('page-title');
    
    // URL se 'slug' ya 'q' (search) nikalo
    const params = new URLSearchParams(window.location.search);
    const categorySlug = params.get('slug'); 
    const searchQuery = params.get('q');

    let apiUrl = '/catalog/skus/';
    let title = 'All Products';

    // --- Logic Start ---
    
    if (categorySlug) {
        // Case A: Category Filter
        // Pehle category ka naam laate hain taaki Title update kar sakein
        try {
            // requireAuth = false rakha hai
            const catResponse = await apiCall(`/catalog/categories/${categorySlug}/`, 'GET', null, false);
            title = catResponse.name;
            
            // Agar Subcategories hain (jaise Snacks ke andar Chips), toh unhe upar dikhao
            if (catResponse.subcategories && catResponse.subcategories.length > 0) {
                const filterContainer = document.getElementById('brand-filters');
                if (filterContainer) {
                    filterContainer.innerHTML = ''; 
                    
                    // "All" Chip
                    const allChip = document.createElement('div');
                    allChip.className = 'chip active';
                    allChip.innerText = `All ${catResponse.name}`;
                    filterContainer.appendChild(allChip);

                    // Subcategory Chips
                    catResponse.subcategories.forEach(sub => {
                        const chip = document.createElement('div');
                        chip.className = 'chip';
                        chip.innerText = sub.name;
                        chip.onclick = () => {
                            // Subcategory par click karne se naya page load hoga
                            window.location.href = `/search_results.html?slug=${sub.slug}`;
                        };
                        filterContainer.appendChild(chip);
                    });
                }
            }
        } catch (e) {
            console.warn("Category info fetch failed, using slug as title");
            title = categorySlug.replace(/-/g, ' ').toUpperCase();
        }

        // Filter API URL
        apiUrl += `?category__slug=${categorySlug}`;

    } else if (searchQuery) {
        // Case B: Search
        apiUrl += `?search=${encodeURIComponent(searchQuery)}`;
        title = `Search: "${searchQuery}"`;
    }

    // Update Page Title
    if(titleEl) titleEl.innerText = title;

    // --- Fetch Products ---
    try {
        // requireAuth = false taaki bina login ke products dikhein
        const response = await apiCall(apiUrl, 'GET', null, false); 
        const products = response.results || response; 

        if (grid) {
            grid.innerHTML = ''; // Loader hatao

            if (products.length === 0) {
                document.getElementById('empty-state').style.display = 'block';
                return;
            }

            products.forEach(p => {
                const card = document.createElement('div');
                card.className = 'prod-card';
                
                const price = parseFloat(p.sale_price).toFixed(0);
                const imgUrl = p.image_url || 'https://cdn-icons-png.flaticon.com/512/1147/1147805.png'; // Generic Placeholder

                card.innerHTML = `
                    <div class="prod-img-box">
                        ${p.is_featured ? '<span class="prod-badge">HOT</span>' : ''}
                        <img src="${imgUrl}" class="prod-img" alt="${p.name}">
                    </div>
                    <div class="prod-title">${p.name}</div>
                    <div class="prod-unit">${p.unit}</div>
                    <div class="prod-footer">
                        <div class="prod-price">₹${price}</div>
                        <button class="prod-add-btn" onclick="addToCart('${p.id}')">ADD</button>
                    </div>
                    <a href="/product.html?code=${p.sku_code}" style="position:absolute; inset:0; z-index:1;"></a>
                `;
                
                // Button ka z-index high karte hain taaki click ho sake
                const btn = card.querySelector('.prod-add-btn');
                btn.style.position = 'relative';
                btn.style.zIndex = '2';

                grid.appendChild(card);
            });
        }

    } catch (error) {
        console.error("Failed to load products", error);
        if (grid) grid.innerHTML = `<p style="color:red; text-align:center;">Error loading products. Check Console.</p>`;
    }
});

// Cart Logic (Auth Required here)
async function addToCart(skuId) {
    if (!localStorage.getItem('accessToken')) {
        // Agar login nahi hai, toh login page par bhejo
        window.location.href = '/auth.html';
        return;
    }
    try {
        // requireAuth = true (default)
        await apiCall('/orders/cart/add/', 'POST', { sku_id: skuId, quantity: 1 });
        // Optionally, show a non-blocking toast or highlight the cart icon here
        if(window.updateGlobalCartCount) window.updateGlobalCartCount();
    } catch (e) {
        // Optionally, show a non-blocking error message
        console.error(e.message || "Failed to add");
    }
}