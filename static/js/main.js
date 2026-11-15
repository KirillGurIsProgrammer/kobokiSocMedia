(() => {
    const appContent = document.querySelector("#app-content");
    const progress = document.querySelector("[data-page-progress]");
    if (!appContent) return;

    let progressTimer = 0;
    let navigationId = 0;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
    history.replaceState({ ...(history.state || {}), scrollY: window.scrollY }, "", location.href);

    function startProgress() {
        if (!progress) return;
        window.clearInterval(progressTimer);
        progress.classList.add("is-loading");
        progress.style.setProperty("--progress-width", "18%");
        let width = 18;
        progressTimer = window.setInterval(() => {
            width = Math.min(88, width + Math.max(1, (92 - width) * 0.08));
            progress.style.setProperty("--progress-width", `${width}%`);
        }, 120);
    }

    function finishProgress() {
        if (!progress) return;
        window.clearInterval(progressTimer);
        progress.style.setProperty("--progress-width", "100%");
        window.setTimeout(() => {
            progress.classList.remove("is-loading");
            progress.style.removeProperty("--progress-width");
        }, reducedMotion.matches ? 0 : 180);
    }

    function isExcludedPath(pathname) {
        return pathname.startsWith("/admin/") || /(?:^|\/)logout(?:\/|$)/i.test(pathname);
    }

    function shouldHandleLink(link, event) {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
        if (link.target || link.hasAttribute("download") || link.closest("[data-no-ajax]") || link.relList.contains("external")) return false;
        const url = new URL(link.href, location.href);
        if (url.origin !== location.origin || url.hash || isExcludedPath(url.pathname)) return false;
        return true;
    }

    function syncShell(nextDocument) {
        const wasAuthenticated = Boolean(document.querySelector(".topbar-profile"));
        const isAuthenticated = Boolean(nextDocument.querySelector(".topbar-profile"));
        if (wasAuthenticated !== isAuthenticated) {
            [".sidebar", ".topbar", ".right-rail"].forEach((selector) => {
                const current = document.querySelector(selector);
                const next = nextDocument.querySelector(selector);
                if (current && next) current.innerHTML = next.innerHTML;
            });
        }
        document.body.classList.toggle("music-page", nextDocument.body.classList.contains("music-page"));
        document.body.toggleAttribute("data-auth-page", nextDocument.body.hasAttribute("data-auth-page"));
        const nextActiveLinks = [...nextDocument.querySelectorAll(".side-nav a.side-link.is-active")].map((link) => link.getAttribute("href"));
        document.querySelectorAll(".side-nav a.side-link").forEach((link) => {
            link.classList.toggle("is-active", nextActiveLinks.includes(link.getAttribute("href")));
        });
        document.title = nextDocument.title;
    }

    function renderResponse(html, destination, { scrollToTop = true, restoreScroll = null } = {}) {
        const nextDocument = new DOMParser().parseFromString(html, "text/html");
        const nextContent = nextDocument.querySelector("#app-content");
        if (!nextContent) throw new Error("The response does not contain #app-content");

        document.dispatchEvent(new CustomEvent("kobokiBeforePageChange", { detail: { url: destination.href } }));
        appContent.innerHTML = nextContent.innerHTML;
        syncShell(nextDocument);
        document.dispatchEvent(new CustomEvent("kobokiPageLoaded", { detail: { url: destination.href } }));

        if (restoreScroll !== null) {
            requestAnimationFrame(() => window.scrollTo(0, restoreScroll));
        } else if (scrollToTop) {
            window.scrollTo(0, 0);
        }
    }

    async function navigate(destination, { push = true, restoreScroll = null } = {}) {
        const url = destination instanceof URL ? destination : new URL(destination, location.href);
        if (push) history.replaceState({ ...(history.state || {}), scrollY: window.scrollY }, "", location.href);
        const requestId = ++navigationId;
        startProgress();
        try {
            const response = await fetch(url.href, {
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest", Accept: "text/html" },
            });
            const contentType = response.headers.get("content-type") || "";
            if (response.status >= 500 || !contentType.includes("text/html")) throw new Error("Page navigation failed");
            const html = await response.text();
            const finalUrl = new URL(response.url || url.href, location.href);
            if (requestId !== navigationId) return;
            if (push) history.pushState({ scrollY: 0 }, "", finalUrl.href);
            renderResponse(html, finalUrl, { scrollToTop: true, restoreScroll });
            if (!push && restoreScroll !== null) history.replaceState({ ...(history.state || {}), scrollY: restoreScroll }, "", finalUrl.href);
        } catch (_) {
            if (requestId === navigationId) location.assign(url.href);
        } finally {
            if (requestId === navigationId) finishProgress();
        }
    }

    function csrfToken(form) {
        const field = form.querySelector("[name=csrfmiddlewaretoken]");
        if (field) return field.value;
        const cookie = document.cookie.split(";").map((item) => item.trim()).find((item) => item.startsWith("csrftoken="));
        return cookie ? decodeURIComponent(cookie.slice("csrftoken=".length)) : "";
    }

    function formHasFiles(form) {
        return Boolean(form.querySelector('input[type="file"]'));
    }

    function excludedForm(form, action) {
        return !appContent.contains(form)
            || form.matches("[data-no-ajax]")
            || Boolean(form.target)
            || formHasFiles(form)
            || action.origin !== location.origin
            || isExcludedPath(action.pathname);
    }

    async function submitForm(form) {
        const method = (form.method || "GET").toUpperCase();
        const action = new URL(form.action || location.href, location.href);
        if (excludedForm(form, action)) {
            form.submit();
            return;
        }

        if (method === "GET") {
            const data = new FormData(form);
            const params = new URLSearchParams(action.search);
            for (const key of new Set(data.keys())) params.delete(key);
            for (const [key, value] of data.entries()) {
                if (typeof value === "string") params.append(key, value);
            }
            action.search = params.toString();
            navigate(action, { push: true });
            return;
        }

        const csrf = csrfToken(form);
        const headers = { "X-Requested-With": "XMLHttpRequest", Accept: "text/html" };
        if (csrf) headers["X-CSRFToken"] = csrf;
        startProgress();
        const requestId = ++navigationId;
        try {
            const response = await fetch(action.href, {
                method,
                body: new FormData(form),
                credentials: "same-origin",
                headers,
            });
            const contentType = response.headers.get("content-type") || "";
            if (response.status >= 500 || !contentType.includes("text/html")) throw new Error("Form response cannot be rendered");
            const html = await response.text();
            const finalUrl = new URL(response.url || action.href, location.href);
            if (requestId !== navigationId) return;
            const redirected = response.redirected || finalUrl.href !== action.href;
            if (redirected) history.pushState({ scrollY: 0 }, "", finalUrl.href);
            renderResponse(html, finalUrl, { scrollToTop: redirected });
        } catch (_) {
            if (requestId === navigationId) form.submit();
        } finally {
            if (requestId === navigationId) finishProgress();
        }
    }

    document.addEventListener("click", (event) => {
        const openConfirm = event.target.closest("[data-confirm-open]");
        if (openConfirm) {
            const dialog = document.getElementById(openConfirm.dataset.confirmOpen);
            if (dialog?.showModal) {
                event.preventDefault();
                dialog.showModal();
                return;
            }
        }
        const closeConfirm = event.target.closest("[data-confirm-close]");
        if (closeConfirm) {
            closeConfirm.closest("dialog")?.close();
            return;
        }
        const link = event.target.closest("a[href]");
        if (!link || !shouldHandleLink(link, event)) return;
        event.preventDefault();
        history.replaceState({ ...(history.state || {}), scrollY: window.scrollY }, "", location.href);
        navigate(new URL(link.href, location.href), { push: true });
    });

    function updateReviewSubmit(form) {
        const submit = form?.querySelector("[data-review-submit]");
        if (submit) submit.disabled = !form.querySelector('input[name="rating"]:checked');
    }
    document.addEventListener("change", (event) => {
        const form = event.target.closest("[data-review-form]");
        if (form && event.target.matches('input[name="rating"]')) updateReviewSubmit(form);
    });
    document.addEventListener("kobokiPageLoaded", () => {
        document.querySelectorAll("[data-review-form]").forEach(updateReviewSubmit);
    });

    document.addEventListener("submit", (event) => {
        const form = event.target.closest("form");
        if (!form || event.defaultPrevented || form.closest("[data-listen-along-join], [data-listen-along-leave], [data-like-form]")) return;
        if (!appContent.contains(form) || form.matches("[data-no-ajax]")) return;
        if (formHasFiles(form)) return;
        const action = new URL(form.action || location.href, location.href);
        if (action.origin !== location.origin || isExcludedPath(action.pathname) || form.target) return;
        event.preventDefault();
        history.replaceState({ ...(history.state || {}), scrollY: window.scrollY }, "", location.href);
        submitForm(form);
    });

    window.addEventListener("popstate", (event) => {
        navigate(location.href, { push: false, restoreScroll: Number.isFinite(event.state?.scrollY) ? event.state.scrollY : 0 });
    });

    document.dispatchEvent(new CustomEvent("kobokiPageLoaded", { detail: { url: location.href, initial: true } }));
})();
