// static/assets/js/utils/assistant.js

document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('ast-btn');
    const box = document.getElementById('ast-box');
    const close = document.getElementById('ast-close');
    const sendBtn = document.getElementById('ast-send');
    const input = document.getElementById('ast-input');
    const msgArea = document.getElementById('ast-msgs');

    if (!btn || !box) return; // Guard clause

    let contextSkuId = null; 

    // --- TOGGLE UI ---
    btn.addEventListener('click', () => {
        if (box.style.display === 'none' || !box.classList.contains('active')) {
            box.style.display = 'flex';
            // Small delay for CSS transition
            setTimeout(() => box.classList.add('active'), 10);
            
            // Auto-start only if empty
            if (msgArea.children.length === 0) {
                sendToBot('start', true); 
            }
            
            // Focus input
            if(input) setTimeout(() => input.focus(), 100);
            
        } else {
            closeBox();
        }
    });

    if (close) close.addEventListener('click', closeBox);

    function closeBox() {
        box.classList.remove('active');
        setTimeout(() => box.style.display = 'none', 300);
    }

    // --- MESSAGING LOGIC ---
    async function handleSend() {
        const text = input.value.trim();
        if (!text) return;

        addMessage(text, 'user');
        input.value = '';

        // Check if we are answering a "How many?" question (Context-Aware)
        if (contextSkuId && !isNaN(text)) {
            try {
                // Updates Cart
                const res = await apiCall('/catalog/assistant/chat/', 'PUT', {
                    quantity: parseInt(text),
                    context_sku_id: contextSkuId
                });
                
                addMessage(res.reply, 'bot');
                
                if (res.action === 'cart_updated') {
                    triggerCartUpdateEffect();
                    contextSkuId = null; // Clear context on success
                }
            } catch (e) {
                console.error("Bot Error", e);
                addMessage("Oops, I couldn't update the cart. Please try again.", 'bot');
            }
        } else {
            // Normal Chat
            sendToBot(text);
        }
    }

    if (sendBtn) sendBtn.addEventListener('click', handleSend);
    if (input) input.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleSend(); });

    async function sendToBot(msg, silent = false) {
        if (!silent) {
            // Optional: Show "typing..." state here
        }

        try {
            // Uses standard apiCall from api.js
            const res = await apiCall('/catalog/assistant/chat/', 'POST', { message: msg });

            // Bot Reply
            addMessage(res.reply, 'bot');

            // Handle Context (e.g., Bot asks "How much Quantity?")
            if (res.context_sku_id) {
                contextSkuId = res.context_sku_id;
            } else {
                contextSkuId = null;
            }

            // Handle Actions
            if (res.action === 'cart_updated') {
                triggerCartUpdateEffect();
            }

        } catch (e) {
            console.error("Bot Network Error", e);
            if (!silent) addMessage("Connection issue. Please try again.", 'bot');
        }
    }

    function addMessage(text, sender) {
        const div = document.createElement('div');
        div.className = `msg-row ${sender}`;
        div.innerHTML = `<div class="msg-bubble ${sender}">${text.replace(/\n/g, '<br>')}</div>`;
        msgArea.appendChild(div);
        msgArea.scrollTop = msgArea.scrollHeight;
    }

    // --- UX HELPERS ---
    function triggerCartUpdateEffect() {
        if (window.updateGlobalCartCount) {
            window.updateGlobalCartCount();
        }
        
        // Visual Pulse on the Bot Icon
        btn.style.transform = "scale(1.2)";
        btn.style.transition = "transform 0.2s ease";
        setTimeout(() => btn.style.transform = "scale(1)", 200);
    }
});