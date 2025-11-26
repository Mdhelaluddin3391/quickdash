document.addEventListener('DOMContentLoaded', () => {
    // 1. URL se ticket ID nikaalein
    // const ticketId = new URLSearchParams(window.location.search).get('id');
    const ticketId = 1; // Dummy ID for UI demo

    const chatMessages = document.getElementById('chat-messages');
    const replyForm = document.getElementById('reply-form');
    const sendBtn = document.getElementById('send-btn');
    const messageInput = document.getElementById('reply-message');

    // --- Function: Naya message bubble add karna ---
    function addMessageBubble(message, isCustomer, userName = null) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', isCustomer ? 'customer' : 'staff');

        let userHtml = '';
        if (userName) {
            userHtml = `<p class="message-user">${userName}</p>`;
        }

        messageDiv.innerHTML = `
            <div class="message-bubble">
                ${userHtml}
                <p class="message-text">${message.text || message.message}</p>
                <span class="message-time">${new Date(message.created_at || Date.now()).toLocaleTimeString()}</span>
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // --- Form Submit Handle karein ---
    if(replyForm) {
        replyForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const messageText = messageInput.value.trim();
            if (!messageText) return;

            sendBtn.disabled = true;
            sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

            // Simulate API Delay
            setTimeout(() => {
                addMessageBubble({ message: messageText, created_at: Date.now() }, true);
                messageInput.value = '';
                sendBtn.disabled = false;
                sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
            }, 500);
        });
    }
});