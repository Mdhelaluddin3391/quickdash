document.addEventListener('DOMContentLoaded', async () => {
    await loadCategories();
    // loadFeaturedProducts(); // Your existing logic for products
});

async function loadCategories() {
    const navContainer = document.getElementById('dynamic-navbar');
    const gridContainer = document.getElementById('home-category-grid');

    try {
        // API Call to get ALL categories
        const response = await apiCall('/catalog/categories/');
        const categories = response.results || response;

        // Filter: Hum sirf PARENT categories chahte hain (jinka parent null hai)
        const parents = categories.filter(c => c.parent === null).sort((a, b) => a.sort_order - b.sort_order);

        // 1. Fill Navbar (Horizontal Scroll)
        // Clear loading text, keep "All"
        navContainer.innerHTML = '<a href="/" class="nav-item active">All</a>';
        
        parents.forEach(cat => {
            const link = document.createElement('a');
            // Link to a listing page filtering by this category slug
            link.href = `/search_results.html?category=${cat.slug}`;
            link.className = 'nav-item';
            link.innerText = cat.name.split(' ')[0]; // Navbar mein naam chhota dikhayein (e.g. "Snacks" instead of "Snacks & Beverages")
            navContainer.appendChild(link);
        });

        // 2. Fill Home Body Grid
        gridContainer.innerHTML = ''; // Clear loader

        parents.forEach(cat => {
            const div = document.createElement('div');
            div.className = 'cat-item-home';
            div.onclick = () => window.location.href = `/search_results.html?category=${cat.slug}`;
            
            // Icon mapping (Optional: You can add real images in DB later)
            // Abhi ke liye DB se icon_url use karenge ya fallback
            const icon = cat.icon_url || 'https://cdn-icons-png.flaticon.com/512/3759/3759344.png';

            div.innerHTML = `
                <div class="cat-icon-box">
                    <img src="${icon}" alt="${cat.name}">
                </div>
                <span class="cat-label">${cat.name}</span>
            `;
            gridContainer.appendChild(div);
        });

    } catch (error) {
        console.error("Error loading categories:", error);
        if(navContainer) navContainer.innerHTML += '<span class="text-danger">Error</span>';
        if(gridContainer) gridContainer.innerHTML = '<p class="text-center text-muted">Failed to load.</p>';
    }
}