document.addEventListener('DOMContentLoaded', () => {
    const chatBox = document.getElementById('chat-box');
    const form = document.getElementById('chat-form');
    const input = document.getElementById('msg-input');

    // Auto-scroll to bottom
    chatBox.scrollTop = chatBox.scrollHeight;

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const msg = input.value.trim();
        if (!msg) return;

        // Append User Message
        appendMessage(msg, 'user');
        input.value = '';

        // Simulate Support Reply (After 1.5s)
        setTimeout(() => {
            appendMessage("Thanks for your message! Our agent will join shortly.", 'staff');
        }, 1500);
    });

    function appendMessage(text, sender) {
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        const div = document.createElement('div');
        div.className = `message ${sender}`;
        div.innerHTML = `
            <div class="bubble">
                ${text}
                <span class="time">${time}</span>
            </div>
        `;
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
    }
});