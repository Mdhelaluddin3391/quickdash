document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('ast-btn');
    const box = document.getElementById('ast-box');
    const close = document.getElementById('ast-close');
    const sendBtn = document.getElementById('ast-send');
    const input = document.getElementById('ast-input');
    const msgArea = document.getElementById('ast-msgs');

    let contextSkuId = null; // To remember product if quantity missing

    // Toggle
    btn.addEventListener('click', () => {
        if (box.style.display === 'none' || !box.classList.contains('active')) {
            box.style.display = 'flex';
            setTimeout(() => box.classList.add('active'), 10);
            if (msgArea.children.length === 0) sendToBot('start', true); // Silent start
        } else {
            box.classList.remove('active');
            setTimeout(() => box.style.display = 'none', 300);
        }
    });

    close.addEventListener('click', () => {
        box.classList.remove('active');
        setTimeout(() => box.style.display = 'none', 300);
    });

    // Send Message
    async function handleSend() {
        const text = input.value.trim();
        if (!text) return;

        addMessage(text, 'user');
        input.value = '';

        // Check if we are answering a "How many?" question
        if (contextSkuId && !isNaN(text)) {
            // Call PUT endpoint
            try {
                const res = await apiCall('/catalog/assistant/chat/', 'PUT', {
                    quantity: text,
                    context_sku_id: contextSkuId
                });
                addMessage(res.reply, 'bot');
                if (res.action === 'cart_updated') {
                    if (window.updateGlobalCartCount) window.updateGlobalCartCount();
                    contextSkuId = null; // Reset
                }
            } catch (e) {
                addMessage("Oops, error updating cart.", 'bot');
            }
        } else {
            // Normal Chat
            sendToBot(text);
        }
    }

    sendBtn.addEventListener('click', handleSend);
    input.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleSend(); });

    async function sendToBot(msg, silent = false) {
        // Typing indicator dikha sakte hain yahan
        if (!silent) {
            // Optional: Add a temporary "Thinking..." bubble
        }

        try {
            const res = await apiCall('/catalog/assistant/chat/', 'POST', { message: msg });

            // Bot Reply
            addMessage(res.reply, 'bot');

            // Context Set (Quantity puchne ke liye)
            if (res.context_sku_id) {
                contextSkuId = res.context_sku_id;
            } else {
                contextSkuId = null;
            }

            // Update Cart Count WITHOUT Redirect
            if (res.action === 'cart_updated') {
                // Sirf Navbar ka number update karega
                if (window.updateGlobalCartCount) {
                    window.updateGlobalCartCount();

                    // Optional: Chhota sa sound ya animation play kar sakte hain
                    const btn = document.getElementById('ast-btn');
                    btn.style.transform = "scale(1.2)";
                    setTimeout(() => btn.style.transform = "scale(1)", 200);
                }
            }

        } catch (e) {
            addMessage("Network issue. Thodi der baad try karein.", 'bot');
        }
    }

    function addMessage(text, sender) {
        const div = document.createElement('div');
        div.className = `msg-row ${sender}`;
        div.innerHTML = `<div class="msg-bubble ${sender}">${text.replace(/\n/g, '<br>')}</div>`;
        msgArea.appendChild(div);
        msgArea.scrollTop = msgArea.scrollHeight;
    }
});