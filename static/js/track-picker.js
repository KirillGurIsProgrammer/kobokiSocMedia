(() => {
    const resultLimit = 20;

    function initializeTrackPickers() {
        document.querySelectorAll("[data-track-picker]").forEach((picker) => {
            if (picker.dataset.initialized) return;
            picker.dataset.initialized = "true";

            const search = picker.querySelector("[data-track-search]");
            const value = picker.querySelector("[data-track-value]");
            const results = picker.querySelector("[data-track-results]");
            const status = picker.querySelector("[data-track-status]");
            const clear = picker.querySelector("[data-track-clear]");
            let requestController;
            let debounceTimer;

            function closeResults() {
                results.hidden = true;
                search.setAttribute("aria-expanded", "false");
            }

            function showStatus(message) {
                status.textContent = message;
                results.hidden = false;
                search.setAttribute("aria-expanded", "true");
            }

            function selectTrack(track) {
                value.value = track.id;
                search.value = track.artist
                    ? `${track.title} — ${track.artist}`
                    : track.title;
                clear.hidden = false;
                results.replaceChildren();
                status.textContent = "";
                closeResults();
            }

            async function loadTracks(query) {
                requestController?.abort();
                requestController = new AbortController();
                results.replaceChildren();
                showStatus("Загрузка треков…");

                const url = new URL(picker.dataset.searchUrl, window.location.origin);
                if (query) url.searchParams.set("q", query);

                try {
                    const response = await fetch(url, {
                        headers: { Accept: "application/json" },
                        signal: requestController.signal,
                    });
                    if (!response.ok) throw new Error(`Track search failed: ${response.status}`);

                    const data = await response.json();
                    if (!Array.isArray(data.results)) {
                        throw new Error("Track search returned an invalid response.");
                    }

                    results.replaceChildren();
                    data.results.slice(0, resultLimit).forEach((track) => {
                        const option = document.createElement("button");
                        option.type = "button";
                        option.className = "track-picker-option";
                        option.setAttribute("role", "option");
                        option.textContent = track.artist
                            ? `${track.title} — ${track.artist}`
                            : track.title;
                        option.addEventListener("click", () => selectTrack(track));
                        results.append(option);
                    });

                    showStatus(
                        data.results.length
                            ? `${data.results.length} трек(ов) найдено.`
                            : "Ничего не найдено.",
                    );
                    if (data.results.length) {
                        results.hidden = false;
                    }
                } catch (error) {
                    if (error.name === "AbortError") return;
                    showStatus("Не удалось загрузить треки. Попробуйте ещё раз.");
                }
            }

            search.addEventListener("focus", () => {
                if (!results.childElementCount && !results.hidden) return;
                if (!value.value) loadTracks(search.value.trim());
            });

            search.addEventListener("input", () => {
                value.value = "";
                clear.hidden = true;
                window.clearTimeout(debounceTimer);
                debounceTimer = window.setTimeout(
                    () => loadTracks(search.value.trim()),
                    200,
                );
            });

            search.addEventListener("keydown", (event) => {
                if (event.key === "Escape") closeResults();
            });

            clear.addEventListener("click", () => {
                value.value = "";
                search.value = "";
                clear.hidden = true;
                results.replaceChildren();
                status.textContent = "";
                closeResults();
                search.focus();
            });

            if (value.value) clear.hidden = false;
        });
    }

    document.addEventListener("kobokiPageLoaded", initializeTrackPickers);
    initializeTrackPickers();
})();
