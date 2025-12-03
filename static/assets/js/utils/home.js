// static/assets/js/utils/home.js

document.addEventListener('DOMContentLoaded', async () => {
    await loadCategories();
    // loadFeaturedProducts(); // Future ke liye
});

async function loadCategories() {
    const navContainer = document.getElementById('dynamic-navbar');
    const gridContainer = document.getElementById('home-category-grid');

    try {
        // 100 categories fetch karein taaki sab aa jayein
        const response = await apiCall('/catalog/categories/?page_size=100', 'GET', null, false);
        const categories = response.results || response;

        // Sirf Parent Categories
        const parents = categories.filter(c => c.parent === null);

        // --- 1. Navbar Update (Smart Naming) ---
        if (navContainer) {
            navContainer.innerHTML = '<a href="/" class="nav-item active">All</a>';
            
            parents.forEach(cat => {
                const link = document.createElement('a');
                link.href = `/search_results.html?slug=${cat.slug}`;
                link.className = 'nav-item';
                
                // [FIX] Yahan hum Clean Name function use karenge
                link.innerText = getCleanName(cat.name);
                
                navContainer.appendChild(link);
            });
        }

        // --- 2. Home Grid Update (Icons ke saath) ---
        if (gridContainer) {
            gridContainer.innerHTML = ''; 

            parents.forEach(cat => {
                const div = document.createElement('div');
                div.className = 'cat-item-home';
                div.onclick = () => window.location.href = `/search_results.html?slug=${cat.slug}`;
                
                const icon = cat.icon_url || 'https://cdn-icons-png.flaticon.com/512/3759/3759344.png';

                div.innerHTML = `
                    <div class="cat-icon-box">
                        <img src="${icon}" alt="${cat.name}">
                    </div>
                    <span class="cat-label">${cat.name}</span>
                `;
                gridContainer.appendChild(div);
            });
        }

    } catch (error) {
        console.error("Error loading categories:", error);
        if(navContainer) navContainer.innerHTML = '<a href="/" class="nav-item active">All</a>';
    }
}

/**
 * [NEW] Helper Function: Category ke lambe naam ko chhota aur sundar banata hai.
 */
function getCleanName(fullName) {
    const map = {
        "Groceries & Essentials": "Groceries",
        "Fresh Produce": "Fruits & Veg",
        "Snacks & Beverages": "Snacks",
        "Dairy, Bread & Eggs": "Dairy",
        "Chicken, Meat & Fish": "Meat",
        "Personal Care": "Personal Care",
        "Home Care": "Home",
        "Instant Food": "Instant",
        "Pet Care": "Pet Care",
        "Baby Care": "Baby Care"
    };
    
    // Agar map mein naam hai toh wo use karo, warna pehla shabd utha lo (bina comma ke)
    return map[fullName] || fullName.split(' ')[0].replace(',', '');
}