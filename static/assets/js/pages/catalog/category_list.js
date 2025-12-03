document.addEventListener('DOMContentLoaded', async () => {
    const grid = document.getElementById('category-grid');
    if (!grid) return;

    // Show Loader
    grid.innerHTML = '<div class="loader">Loading categories...</div>';

    try {
        // Fetch all active categories
        const response = await apiCall('/catalog/categories/?page_size=50', 'GET', null, false); // false = no auth needed
        const categories = response.results || response;

        grid.innerHTML = ''; // Clear loader

        if (categories.length === 0) {
            grid.innerHTML = '<p class="text-muted text-center col-12">No categories found.</p>';
            return;
        }

        // Render Categories
        categories.forEach(cat => {
            // Only show Parent categories (Top level)
            if (!cat.parent) {
                const card = document.createElement('a');
                card.href = `/search_results.html?slug=${cat.slug}`;
                card.className = 'cat-card';
                
                const icon = cat.icon_url || 'https://cdn-icons-png.flaticon.com/512/2921/2921822.png'; // Default Icon

                card.innerHTML = `
                    <img src="${icon}" alt="${cat.name}" class="cat-img">
                    <div class="cat-name">${cat.name}</div>
                `;
                grid.appendChild(card);
            }
        });

    } catch (e) {
        console.error("Category Load Error:", e);
        grid.innerHTML = `<p class="error-msg">Failed to load categories. Please refresh.</p>`;
    }
});