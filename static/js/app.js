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