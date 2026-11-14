document.addEventListener("DOMContentLoaded", () => {
    const input = document.querySelector(".track-form input[type='file']");
    const picker = input?.closest(".file-picker");
    const fileName = picker?.querySelector("[data-file-name]");

    if (!input || !picker || !fileName) return;

    input.addEventListener("change", () => {
        const file = input.files?.[0];
        fileName.textContent = file?.name || "Файл не выбран";
        picker.classList.toggle("has-file", Boolean(file));
    });
});
