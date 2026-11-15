(() => {
    function setStatus(form, message, isError = false) {
        const status = form.querySelector("[data-interaction-status]");
        if (!status) return;
        status.textContent = message;
        status.classList.toggle("is-error", isError);
    }

    function updateCommentCount(card, count) {
        const counter = card?.querySelector("[data-comment-count]");
        if (counter) counter.textContent = count;
    }

    function appendComment(container, comment, prepend = false) {
        const emptyState = container.querySelector("[data-empty-comments]");
        emptyState?.remove();

        const item = document.createElement("article");
        item.className = "post-comment";
        item.dataset.commentItem = "";
        const author = document.createElement("a");
        author.href = comment.author_url;
        const name = document.createElement("strong");
        name.textContent = comment.author;
        author.append(name);
        const text = document.createElement("p");
        text.textContent = comment.text;
        item.append(author, text);
        container.insertBefore(item, prepend ? container.firstChild : null);
    }

    async function submitForm(form) {
        const button = form.querySelector("button[type='submit']");
        if (button) button.disabled = true;
        setStatus(form, "");

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),
                headers: { Accept: "application/json" },
                credentials: "same-origin",
            });
            if (response.redirected) {
                window.location.assign(response.url);
                return;
            }

            const data = await response.json();
            if (!response.ok) {
                setStatus(form, data.error || "Не удалось выполнить действие.", true);
                return;
            }

            if (form.matches("[data-post-like-form]")) {
                const buttonElement = form.querySelector(".post-like-button");
                const heart = buttonElement.querySelector("[aria-hidden='true']");
                const count = buttonElement.querySelector("[data-like-count]");
                buttonElement.classList.toggle("is-liked", data.liked);
                buttonElement.setAttribute("aria-pressed", String(data.liked));
                heart.textContent = data.liked ? "♥" : "♡";
                count.textContent = data.like_count;
                return;
            }

            const card = form.closest(".post-card");
            const commentsList = document.querySelector(
                ".comments [data-comment-list]",
            );
            if (commentsList) {
                appendComment(commentsList, data);
            }

            const preview = card?.querySelector("[data-comment-preview]");
            if (preview) {
                const previewItems = preview.querySelectorAll("[data-comment-item]");
                if (!previewItems.length) {
                    const author = document.createElement("a");
                    author.href = data.author_url;
                    const name = document.createElement("strong");
                    name.textContent = data.author;
                    author.append(name);
                    const text = document.createElement("p");
                    text.textContent = data.text;
                    const item = document.createElement("article");
                    item.className = "post-comment";
                    item.dataset.commentItem = "";
                    item.append(author, text);
                    preview.insertBefore(item, form);
                } else {
                    appendComment(preview, data, true);
                    const updatedItems = preview.querySelectorAll("[data-comment-item]");
                    if (updatedItems.length > 3) updatedItems[updatedItems.length - 1].remove();
                }
            }

            updateCommentCount(card, data.comment_count);
            form.reset();
            setStatus(form, "Комментарий добавлен.");
        } catch {
            setStatus(form, "Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.", true);
        } finally {
            if (button) button.disabled = false;
        }
    }

    document.addEventListener("submit", (event) => {
        if (event.defaultPrevented) return;
        const form = event.target.closest("[data-post-like-form], [data-post-comment-form]");
        if (!form) return;
        event.preventDefault();
        submitForm(form);
    });
})();
