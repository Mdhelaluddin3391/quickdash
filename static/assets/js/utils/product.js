// assets/js/product.js

document.addEventListener('DOMContentLoaded', async () => {
    // URL se 'code' parameter nikalo (e.g. product.html?code=MILK-AMUL)
    const params = new URLSearchParams(window.location.search);
    const skuCode = params.get('code');

    if (!skuCode) return;

    try {
        // SKU Detail API Call
        const product = await apiCall(`/catalog/skus/${skuCode}/`);
        
        // HTML Elements Update karo
        document.querySelector('.product-name').innerText = product.name;
        document.querySelector('.product-quantity-desc').innerText = `${product.unit} • ${product.brand_name || ''}`;
        document.querySelector('.current-price').innerText = `₹${product.sale_price}`;
        
        const img = document.querySelector('.product-image-container img');
        if(product.image_url) img.src = product.image_url;

        // Description Populate
        const descContainer = document.querySelector('.product-description p');
        descContainer.innerText = product.description || "No description available.";

        // Add to Cart Button Logic
        const addBtn = document.querySelector('.add-to-cart-btn');
        addBtn.onclick = () => window.addToCart(product.id);

    } catch (e) {
        alert("Product not found");
        window.location.href = 'index.html';
    }
});
