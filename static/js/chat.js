document.addEventListener("contextmenu", (event) => {
    const message = event.target.closest(".message-card--mine");
    if (!message) return;

    const form = message.querySelector(".delete-message-form");
    if (!form) return;
    event.preventDefault();
    document.querySelectorAll(".delete-message-form").forEach((item) => {
        item.hidden = true;
    });
    form.hidden = false;
});

document.addEventListener("click", (event) => {
    if (event.target.closest(".delete-message-form") || event.target.closest(".message-card--mine")) return;
    document.querySelectorAll(".delete-message-form").forEach((item) => {
        item.hidden = true;
    });
});
