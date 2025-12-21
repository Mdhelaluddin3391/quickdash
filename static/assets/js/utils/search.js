// static/assets/js/utils/search.js

document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.querySelector('input[name="q"]');
    // Support multiple search bars (desktop/mobile) by targeting the closest container
    const searchForm = document.querySelector('.search-bar-row') || searchInput?.closest('form');
    
    if (!searchInput || !searchForm) return;

    // 1. Initialize Dropdown (Singleton Pattern)
    let suggestBox = document.getElementById('search-suggestions');
    if (!suggestBox) {
        suggestBox = document.createElement('div');
        suggestBox.id = 'search-suggestions';
        suggestBox.className = 'search-dropdown';
        suggestBox.style.display = 'none';
        
        // Append correctly based on layout
        const container = searchForm.style.position === 'relative' ? searchForm : searchForm.parentElement;
        if(getComputedStyle(container).position === 'static') container.style.position = 'relative';
        container.appendChild(suggestBox);
    }

    let debounceTimer;
    let currentController = null; 

    // 2. Input Listener (Typing)
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        
        clearTimeout(debounceTimer);
        
        if (query.length < 2) {
            suggestBox.style.display = 'none';
            return;
        }

        // 300ms Debounce
        debounceTimer = setTimeout(() => fetchSuggestions(query), 300);
    });

    // 3. Focus Listener
    searchInput.addEventListener('focus', () => {
        if (searchInput.value.trim().length >= 2 && suggestBox.innerHTML !== '') {
            suggestBox.style.display = 'block';
        }
    });

    // 4. API Call with AbortController
    async function fetchSuggestions(query) {
        // Cancel previous pending request
        if (currentController) {
            currentController.abort();
        }
        currentController = new AbortController();
        const signal = currentController.signal;

        try {
            // Get Config
            const apiBase = (window.APP_CONFIG && window.APP_CONFIG.API_BASE) ? window.APP_CONFIG.API_BASE : '/api/v1';
            
            // Prepare Headers
            const headers = { 'Content-Type': 'application/json' };
            const token = localStorage.getItem('access_token'); // FIX: Correct key name
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            // Fetch
            const response = await fetch(`${apiBase}/catalog/suggest/?q=${encodeURIComponent(query)}`, {
                method: 'GET',
                headers: headers,
                signal: signal
            });

            if (!response.ok) throw new Error("Search failed");

            const results = await response.json();
            renderSuggestions(results);

        } catch (e) {
            if (e.name === 'AbortError') {
                // Ignore cancellations
            } else {
                console.warn("[Search] Error:", e);
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
            
            // Use Backend provided URL or fallback to search results
            div.href = item.url || `/search_results.html?q=${encodeURIComponent(item.text)}`;
            div.className = 'suggest-item';
            div.style.textDecoration = 'none';
            div.style.display = 'flex';
            div.style.alignItems = 'center';
            div.style.padding = '10px';
            div.style.borderBottom = '1px solid #eee';
            
            if (item.type === 'category') {
                div.innerHTML = `
                    <div class="s-icon" style="margin-right:10px; width:30px; text-align:center;">
                        <i class="${item.icon || 'fas fa-tag'} text-muted"></i>
                    </div>
                    <div class="s-info">
                        <div class="s-main" style="font-weight:600; color:#333;">${item.text}</div>
                        <div class="s-sub" style="font-size:0.8rem; color:#888;">Category</div>
                    </div>
                `;
            } else {
                const img = item.image || '/static/assets/img/placeholder.png';
                const price = item.price ? `₹${parseFloat(item.price).toFixed(0)}` : '';
                
                div.innerHTML = `
                    <img src="${img}" class="s-img" alt="img" style="width:40px; height:40px; object-fit:cover; border-radius:4px; margin-right:10px;">
                    <div class="s-info" style="flex:1;">
                        <div class="s-main" style="font-weight:500; color:#333;">${item.text}</div>
                        <div class="s-sub" style="font-size:0.8rem; color:#888;">${item.sub_text || 'Product'}</div>
                    </div>
                    <div class="s-price" style="font-weight:bold; color:#32CD32;">${price}</div>
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