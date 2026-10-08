setTimeout(() => {
    const messages = document.querySelectorAll(".flash-message");

    messages.forEach(message => {
        message.style.display = "none";
    });
}, 5000);

const navToggle = document.querySelector(".nav-toggle");
const navLinks = document.querySelector(".nav-links");

navToggle.addEventListener("click", () => {
    const isOpen = navLinks.classList.toggle("is-open");
    navToggle.setAttribute("aria-expanded", isOpen);
});

// ---- Game 11 helper chat ----
const chatToggle = document.getElementById("chatToggle");
const chatBox = document.getElementById("chatBox");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatMessages = document.getElementById("chatMessages");

if (chatToggle && chatBox && chatForm) {
    chatToggle.addEventListener("click", () => {
        chatBox.classList.toggle("is-open");
        if (chatBox.classList.contains("is-open")) {
            chatInput.focus();
        }
    });

    const addChatMessage = (text, who) => {
        const div = document.createElement("div");
        div.className = "chat-msg chat-" + who;
        div.textContent = text;
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return div;
    };

    chatForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const question = chatInput.value.trim();
        if (!question) return;

        addChatMessage(question, "me");
        chatInput.value = "";
        const waiting = addChatMessage("Thinking...", "bot");

        try {
            const response = await fetch("/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: question }),
            });
            const data = await response.json();
            waiting.textContent = data.answer;
        } catch (error) {
            waiting.textContent = "Sorry, something went wrong. Please try again.";
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });
}