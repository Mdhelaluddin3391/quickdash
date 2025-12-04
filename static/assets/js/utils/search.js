document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.querySelector('input[name="q"]');
    const searchForm = document.querySelector('.search-bar-row');
    
    if (!searchInput || !searchForm) return;

    // 1. Dropdown Banayein
    let suggestBox = document.getElementById('search-suggestions');
    if (!suggestBox) {
        suggestBox = document.createElement('div');
        suggestBox.id = 'search-suggestions';
        suggestBox.className = 'search-dropdown';
        suggestBox.style.display = 'none';
        searchForm.appendChild(suggestBox);
    }

    let debounceTimer;
    let currentController = null; // Purani request cancel karne ke liye

    // 2. Input Listener (Typing)
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        
        clearTimeout(debounceTimer);
        
        if (query.length < 2) {
            suggestBox.style.display = 'none';
            return;
        }

        // 300ms ka wait (Debounce)
        debounceTimer = setTimeout(() => fetchSuggestions(query), 300);
    });

    // 3. Focus Listener (Dobara click karne par dikhaye)
    searchInput.addEventListener('focus', () => {
        if (searchInput.value.trim().length >= 2 && suggestBox.innerHTML !== '') {
            suggestBox.style.display = 'block';
        }
    });

    // 4. API Call with AbortController
    async function fetchSuggestions(query) {
        // Agar pehle se koi request chal rahi hai, toh use cancel karo
        if (currentController) {
            currentController.abort();
        }
        currentController = new AbortController();
        const signal = currentController.signal;

        try {
            // Note: apiCall function ko modify karna pad sakta hai signal support ke liye,
            // lekin standard fetch directly use karte hain yahan better control ke liye.
            const token = localStorage.getItem('accessToken');
            const headers = { 'Content-Type': 'application/json' };
            // Search public hai, par agar user login hai toh token bhej sakte hain (optional)
            
            const response = await fetch(`${APP_CONFIG.API_BASE}/catalog/suggest/?q=${encodeURIComponent(query)}`, {
                method: 'GET',
                headers: headers,
                signal: signal
            });

            if (!response.ok) throw new Error("Search failed");

            const results = await response.json();
            renderSuggestions(results);

        } catch (e) {
            if (e.name === 'AbortError') {
                console.log("Old search cancelled"); // Expected behavior
            } else {
                console.error("Search error:", e);
            }
        }
    }

    // 5. Render List
    function renderSuggestions(data) {
        if (!data || data.length === 0) {
            suggestBox.style.display = 'none';
            return;
        }

        suggestBox.innerHTML = '';
        
        data.forEach(item => {
            const div = document.createElement('a');
            div.href = item.url;
            div.className = 'suggest-item';
            
            if (item.type === 'category') {
                div.innerHTML = `
                    <div class="s-icon"><i class="${item.icon}"></i></div>
                    <div class="s-info">
                        <span class="s-main">${item.text}</span>
                        <span class="s-sub">Category</span>
                    </div>
                `;
            } else {
                const img = item.image || 'https://via.placeholder.com/40';
                // Price formatting check
                const price = item.price ? `₹${parseFloat(item.price).toFixed(0)}` : '';
                
                div.innerHTML = `
                    <img src="${img}" class="s-img" alt="img">
                    <div class="s-info">
                        <span class="s-main">${item.text}</span>
                        <span class="s-sub">${item.sub_text}</span>
                    </div>
                    <div class="s-price">${price}</div>
                `;
            }
            suggestBox.appendChild(div);
        });

        suggestBox.style.display = 'block';
    }

    // 6. Click Outside to Close
    document.addEventListener('click', (e) => {
        if (!searchForm.contains(e.target)) {
            suggestBox.style.display = 'none';
        }
    });
});