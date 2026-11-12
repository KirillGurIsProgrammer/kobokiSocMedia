(() => {
    const player = document.querySelector("[data-music-player]");
    if (!player) return;

    const audio = player.querySelector("audio");
    const title = player.querySelector("[data-player-title]");
    const artist = player.querySelector("[data-player-artist]");
    const cover = player.querySelector("[data-player-cover]");
    const toggle = player.querySelector("[data-player-toggle]");
    const seek = player.querySelector("[data-player-seek]");
    const currentTime = player.querySelector("[data-player-current]");
    const duration = player.querySelector("[data-player-duration]");
    const queueList = player.querySelector("[data-queue-items]");
    const queuePanel = player.querySelector("[data-player-queue]");
    const queueToggle = player.querySelector("[data-queue-toggle]");
    const playerLikeForm = player.querySelector("[data-player-like-form]");
    const playerLikeUrl = playerLikeForm.action;
    const playerLikeButton = player.querySelector("[data-player-like]");
    const storageKey = "koboki.music-player.v1";
    let queue = [];
    let queueIndex = -1;
    let activeTrack = null;
    let restoring = false;

    const formatTime = (seconds) => {
        if (!Number.isFinite(seconds)) return "0:00";
        const value = Math.floor(seconds);
        return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
    };

    function saveState() {
        if (!activeTrack) return;
        try {
            sessionStorage.setItem(storageKey, JSON.stringify({
                track: activeTrack,
                queue,
                queueIndex,
                position: audio.currentTime || 0,
                volume: audio.volume,
                wasPlaying: !audio.paused,
            }));
        } catch (_) { /* Storage can be unavailable in private browsing. */ }
    }

    function renderQueue() {
        queueList.replaceChildren();
        queue.forEach((track, index) => {
            const item = document.createElement("li");
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = `${track.title} — ${track.artist}`;
            button.setAttribute("aria-current", index === queueIndex ? "true" : "false");
            button.addEventListener("click", () => playIndex(index));
            item.append(button);
            queueList.append(item);
        });
    }

    function paintTrack(track) {
        title.textContent = track.title || "Без названия";
        artist.textContent = track.artist || "Неизвестный исполнитель";
        if (track.cover) {
            cover.style.backgroundImage = `url("${CSS.escape(track.cover)}")`;
            cover.classList.add("has-cover");
            cover.querySelector("span").hidden = true;
        } else {
            cover.style.backgroundImage = "";
            cover.classList.remove("has-cover");
            cover.querySelector("span").hidden = false;
        }
        seek.disabled = false;
        playerLikeForm.dataset.trackId = track.id;
        playerLikeForm.action = playerLikeUrl.replace(/0\/like\/$/, `${track.id}/like/`);
        playerLikeButton.disabled = false;
        playerLikeButton.textContent = track.liked ? "♥" : "♡";
        playerLikeButton.classList.toggle("is-liked", Boolean(track.liked));
        playerLikeButton.setAttribute("aria-pressed", String(Boolean(track.liked)));
        playerLikeButton.setAttribute("aria-label", track.liked ? "Убрать из понравившихся" : "Нравится");
        player.querySelector(".music-player-like-count").textContent = track.likeCount || "";
    }

    function setTrack(track, index = -1, shouldPlay = true) {
        activeTrack = track;
        queueIndex = index;
        audio.src = track.url;
        audio.load();
        paintTrack(track);
        renderQueue();
        if (shouldPlay) audio.play().catch(() => {});
        saveState();
    }

    function playIndex(index) {
        if (index < 0 || index >= queue.length) return;
        setTrack(queue[index], index, true);
    }

    function trackFromButton(button) {
        const row = button.closest("[data-track-id]");
        return {
            id: button.dataset.trackId,
            url: button.dataset.trackUrl,
            title: button.dataset.trackTitle,
            artist: button.dataset.trackArtist,
            cover: button.dataset.trackCover || "",
            playlistId: button.dataset.playlistId || "",
            liked: row?.dataset.liked === "true",
            likeCount: Number(row?.dataset.likeCount || 0),
        };
    }

    function playFromButton(button) {
        const list = button.closest("[data-track-list]");
        queue = list ? Array.from(list.querySelectorAll("[data-track-play]"), trackFromButton) : [trackFromButton(button)];
        queueIndex = queue.findIndex((track) => track.id === button.dataset.trackId);
        playIndex(queueIndex);
    }

    player.addEventListener("click", (event) => {
        const button = event.target.closest("button");
        if (!button) return;
        if (button.matches("[data-player-toggle]")) {
            if (!activeTrack) return;
            if (audio.paused) audio.play().catch(() => {});
            else audio.pause();
        } else if (button.matches("[data-player-previous]")) {
            if (audio.currentTime > 3) audio.currentTime = 0;
            else playIndex(queueIndex - 1);
        } else if (button.matches("[data-player-next]")) {
            playIndex(queueIndex + 1);
        } else if (button.matches("[data-queue-toggle]")) {
            const opening = queuePanel.hidden;
            queuePanel.hidden = !opening;
            button.setAttribute("aria-expanded", String(opening));
        }
    });

    document.addEventListener("click", (event) => {
        const playlistButton = event.target.closest("[data-play-playlist]");
        if (playlistButton) {
            const playlistId = playlistButton.dataset.playlistId;
            const list = document.querySelector(`[data-playlist-track-list="${CSS.escape(playlistId)}"]`);
            if (!list) return;
            queue = Array.from(list.querySelectorAll("[data-track-play]"), (button) => {
                const track = trackFromButton(button);
                track.playlistId = playlistId;
                if (playlistButton.dataset.playlistCover) track.cover = playlistButton.dataset.playlistCover;
                return track;
            });
            queueIndex = 0;
            playIndex(queueIndex);
            return;
        }
        const playButton = event.target.closest("[data-track-play]");
        if (playButton) {
            event.preventDefault();
            playFromButton(playButton);
            return;
        }
        const link = event.target.closest("a[href]");
        if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        if (link.target || link.hasAttribute("download")) return;
        const url = new URL(link.href, location.href);
        if (url.origin === location.origin && url.pathname === location.pathname && url.search === location.search && url.hash) return;
        if (url.origin !== location.origin || url.pathname.startsWith("/admin/")) return;
        event.preventDefault();
        navigate(url.href, true);
    });

    document.addEventListener("submit", async (event) => {
        const form = event.target.closest("[data-like-form]");
        if (!form) return;
        event.preventDefault();
        const id = form.dataset.trackId;
        const csrf = form.querySelector("[name=csrfmiddlewaretoken]")?.value;
        if (!id || !csrf) {
            form.submit();
            return;
        }
        try {
            const response = await fetch(form.action, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrf,
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify({ track_id: id }),
            });
            if (!response.ok) throw new Error("Не удалось изменить отметку");
            const result = await response.json();
            document.querySelectorAll("[data-like-form]").forEach((likeForm) => {
                if (likeForm.dataset.trackId !== id) return;
                const button = likeForm.querySelector("button[type=submit]");
                if (!button) return;
                button.textContent = result.liked ? "♥" : "♡";
                button.classList.toggle("is-liked", result.liked);
                button.setAttribute("aria-pressed", String(result.liked));
                button.setAttribute("aria-label", result.liked ? "Убрать из понравившихся" : "Нравится");
                const count = likeForm.querySelector("[data-like-count]");
                if (count) count.textContent = result.like_count;
            });
            document.querySelectorAll("[data-track-id]").forEach((row) => {
                if (row.dataset.trackId === id) {
                    row.dataset.liked = String(result.liked);
                    row.dataset.likeCount = String(result.like_count);
                }
            });
            if (activeTrack?.id === id) {
                activeTrack.liked = result.liked;
                activeTrack.likeCount = result.like_count;
                saveState();
            }
        } catch (_) {
            form.submit();
        }
    });

    async function navigate(url, push) {
        try {
            const response = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
            if (!response.ok || !response.headers.get("content-type")?.includes("text/html")) throw new Error("Page navigation failed");
            const html = await response.text();
            const nextDocument = new DOMParser().parseFromString(html, "text/html");
            const nextMain = nextDocument.querySelector(".site-main");
            const currentMain = document.querySelector(".site-main");
            if (!nextMain || !currentMain) throw new Error("Music layout not found");
            currentMain.innerHTML = nextMain.innerHTML;
            document.title = nextDocument.title;
            if (push) history.pushState({}, "", url);
            window.scrollTo(0, 0);
        } catch (_) {
            location.assign(url);
        }
    }

    window.addEventListener("popstate", () => navigate(location.href, false));
    audio.addEventListener("play", () => { toggle.textContent = "Ⅱ"; toggle.setAttribute("aria-label", "Пауза"); saveState(); });
    audio.addEventListener("pause", () => { toggle.textContent = "▶"; toggle.setAttribute("aria-label", "Воспроизвести"); saveState(); });
    audio.addEventListener("timeupdate", () => {
        currentTime.textContent = formatTime(audio.currentTime);
        duration.textContent = formatTime(audio.duration);
        if (Number.isFinite(audio.duration) && audio.duration > 0) seek.value = String(Math.round(audio.currentTime / audio.duration * 1000));
        saveState();
    });
    audio.addEventListener("loadedmetadata", () => {
        duration.textContent = formatTime(audio.duration);
        if (restoring && activeTrack) {
            const state = restoring;
            audio.currentTime = Math.min(state.position || 0, audio.duration || 0);
            restoring = false;
            if (state.wasPlaying) audio.play().catch(() => {});
        }
    });
    audio.addEventListener("ended", () => playIndex(queueIndex + 1));
    seek.addEventListener("input", () => {
        if (Number.isFinite(audio.duration)) audio.currentTime = Number(seek.value) / 1000 * audio.duration;
    });
    seek.addEventListener("change", saveState);
    player.querySelector("[data-player-volume]").addEventListener("input", (event) => {
        audio.volume = Number(event.target.value);
        saveState();
    });
    document.addEventListener("keydown", (event) => {
        const target = event.target;
        if (event.code !== "Space" || target.matches("input, textarea, select, button, [contenteditable='true']")) return;
        event.preventDefault();
        if (!activeTrack) return;
        if (audio.paused) audio.play().catch(() => {});
        else audio.pause();
    });

    try {
        const state = JSON.parse(sessionStorage.getItem(storageKey) || "null");
        if (state?.track?.url) {
            queue = Array.isArray(state.queue) ? state.queue : [state.track];
            queueIndex = Number.isInteger(state.queueIndex) ? state.queueIndex : 0;
            restoring = state;
            setTrack(state.track, queueIndex, false);
            audio.volume = Number.isFinite(state.volume) ? state.volume : 0.8;
            player.querySelector("[data-player-volume]").value = String(audio.volume);
            renderQueue();
        }
    } catch (_) { /* Ignore malformed or unavailable session state. */ }
})();
