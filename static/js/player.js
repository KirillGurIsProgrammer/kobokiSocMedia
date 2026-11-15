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
    const nowPlayingUrl = player.dataset.nowPlayingUrl;
    const listenBanner = player.querySelector("[data-listen-along-banner]");
    const storageKey = "koboki.music-player.v1";
    let queue = [];
    let queueIndex = -1;
    let activeTrack = null;
    let restoring = false;
    let joinedHost = null;
    let syncInFlight = false;
    let toastTimer = 0;
    let radioMode = null;
    let radioLoading = false;
    let radioGeneration = 0;
    let radioStartOnLoad = false;
    let audioContext = null;
    let mediaSource = null;
    let equalizer = [];
    let compressor = null;
    let outputGain = null;
    let expanded = false;
    let previousFocus = null;
    const soundKey = "koboki.music-sound.v1";
    const frequencies = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000];

    function ensureAudioGraph() {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) return;
        try {
            if (!audioContext) {
                audioContext = new AudioContextClass();
                mediaSource = audioContext.createMediaElementSource(audio);
                equalizer = frequencies.map((frequency, index) => {
                    const filter = audioContext.createBiquadFilter();
                    filter.type = index === 0 ? "lowshelf" : index === 9 ? "highshelf" : "peaking";
                    filter.frequency.value = frequency;
                    if (filter.type === "peaking") filter.Q.value = 1;
                    return filter;
                });
                compressor = audioContext.createDynamicsCompressor();
                outputGain = audioContext.createGain();
                mediaSource.connect(equalizer[0]);
                equalizer.forEach((filter, index) => filter.connect(equalizer[index + 1] || compressor));
                compressor.connect(outputGain);
                outputGain.connect(audioContext.destination);
                restoreSoundSettings();
                audio.addEventListener("timeupdate", updateCompressionMeter);
            }
            if (audioContext.state === "suspended") audioContext.resume().catch(() => {});
        } catch (_) {
            showToast("Обработка звука недоступна в этом браузере");
        }
    }

    function soundControls() {
        return {
            eqEnabled: player.querySelector("[data-eq-enabled]"),
            eqBands: [...player.querySelectorAll("[data-eq-band]")],
            eqPreset: player.querySelector("[data-eq-preset]"),
            compressorPreset: player.querySelector("[data-compressor-preset]"),
            compressorInputs: [...player.querySelectorAll("[data-compressor]")],
        };
    }

    function saveSoundSettings() {
        const controls = soundControls();
        const settings = {
            eqEnabled: controls.eqEnabled.checked,
            bands: controls.eqBands.map((input) => Number(input.value)),
            compressorPreset: controls.compressorPreset.value,
            compressor: Object.fromEntries(controls.compressorInputs.map((input) => [input.dataset.compressor, Number(input.value)])),
        };
        try { localStorage.setItem(soundKey, JSON.stringify(settings)); } catch (_) { /* Storage can be unavailable. */ }
    }

    function applySoundSettings() {
        if (!audioContext) return;
        const controls = soundControls();
        controls.eqBands.forEach((input, index) => {
            equalizer[index].gain.setTargetAtTime(controls.eqEnabled.checked ? Number(input.value) : 0, audioContext.currentTime, 0.02);
        });
        controls.compressorInputs.forEach((input) => {
            const target = input.dataset.compressor === "makeup" ? outputGain.gain : compressor[input.dataset.compressor];
            const value = input.dataset.compressor === "makeup" ? 10 ** (Number(input.value) / 20) : Number(input.value);
            target.setTargetAtTime(value, audioContext.currentTime, 0.03);
            const output = input.parentElement.querySelector("output");
            if (output) output.value = `${Number(input.value).toFixed(input.step === "any" ? 1 : 2)}${input.dataset.compressor === "makeup" ? " дБ" : ""}`;
        });
        updateCompressionMeter();
    }

    function restoreSoundSettings() {
        try {
            const saved = JSON.parse(localStorage.getItem(soundKey) || "null");
            if (saved) {
                const controls = soundControls();
                controls.eqEnabled.checked = saved.eqEnabled !== false;
                controls.eqBands.forEach((input, index) => { input.value = String(saved.bands?.[index] ?? 0); });
                controls.compressorPreset.value = saved.compressorPreset || "off";
                controls.compressorInputs.forEach((input) => { if (saved.compressor?.[input.dataset.compressor] != null) input.value = String(saved.compressor[input.dataset.compressor]); });
            }
        } catch (_) { /* Ignore malformed settings. */ }
        applySoundSettings();
    }

    function setEqualizerPreset(name) {
        const values = {
            flat: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            bass: [6, 5, 3, 1, 0, 0, 0, 1, 2, 3],
            vocal: [-2, -1, 0, 2, 3, 3, 2, 1, 0, -1],
            night: [-3, -2, 0, 2, 2, 1, 0, -1, -2, -3],
        };
        if (!values[name]) return;
        soundControls().eqBands.forEach((input, index) => { input.value = String(values[name][index]); });
        soundControls().eqPreset.value = name;
        applySoundSettings();
        saveSoundSettings();
    }

    function setCompressorPreset(name) {
        const presets = {
            off: [0, 0, 1, 0.003, 0.25, 0],
            soft: [-18, 24, 3, 0.01, 0.2, 2],
            night: [-30, 30, 6, 0.02, 0.35, 5],
        };
        if (!presets[name]) return;
        soundControls().compressorInputs.forEach((input, index) => { input.value = String(presets[name][index]); });
        soundControls().compressorPreset.value = name;
        applySoundSettings();
        saveSoundSettings();
    }

    function updateCompressionMeter() {
        const meter = player.querySelector("[data-compressor-reduction]");
        if (meter) meter.textContent = `Сжатие: ${compressor ? Math.round(compressor.reduction) : 0} дБ`;
    }

    function setExpanded(value) {
        expanded = value;
        player.classList.toggle("is-expanded", expanded);
        document.body.classList.toggle("player-expanded", expanded);
        player.setAttribute("role", expanded ? "dialog" : "region");
        player.setAttribute("aria-modal", String(expanded));
        player.querySelector("[data-player-expand]").setAttribute("aria-pressed", String(expanded));
        player.querySelector("[data-player-close]").hidden = !expanded;
        if (expanded) {
            previousFocus = document.activeElement;
            player.querySelector("[data-player-close]").focus();
        } else {
            previousFocus?.focus?.();
            previousFocus = null;
        }
    }

    const formatTime = (seconds) => {
        if (!Number.isFinite(seconds)) return "0:00";
        const value = Math.floor(seconds);
        return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
    };

    function showToast(message) {
        const toast = player.querySelector("[data-music-toast]");
        if (!toast) return;
        toast.textContent = message;
        toast.hidden = false;
        window.clearTimeout(toastTimer);
        toastTimer = window.setTimeout(() => { toast.hidden = true; }, 2400);
    }

    function closeTrackMenu(element) {
        const menu = element.closest("details");
        if (!menu) return;
        menu.open = false;
        menu.querySelector("summary")?.focus();
    }

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

    function sendNowPlaying(isPlaying = !audio.paused, beacon = false) {
        if (!activeTrack?.id || !nowPlayingUrl) return;
        const csrf = playerLikeForm.querySelector("[name=csrfmiddlewaretoken]")?.value;
        if (!csrf) return;
        const payload = {
            track_id: activeTrack.id,
            playlist_id: activeTrack.playlistId || null,
            position_seconds: audio.currentTime || 0,
            duration_seconds: Number.isFinite(audio.duration) ? audio.duration : 0,
            is_playing: Boolean(isPlaying),
        };
        if (beacon && navigator.sendBeacon) {
            const formData = new FormData();
            Object.entries(payload).forEach(([key, value]) => formData.append(key, value ?? ""));
            formData.append("csrfmiddlewaretoken", csrf);
            navigator.sendBeacon(nowPlayingUrl, formData);
            return;
        }
        fetch(nowPlayingUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrf,
                "X-Requested-With": "XMLHttpRequest",
            },
            body: JSON.stringify(payload),
        }).then((response) => response.ok ? response.json() : null).then((result) => {
            if (!result || !Number.isFinite(result.listener_count)) return;
            player.querySelectorAll("[data-host-listener-count]").forEach((counter) => {
                counter.textContent = `С вами слушают: ${result.listener_count}`;
                counter.hidden = false;
            });
        }).catch(() => {});
    }

    function renderQueue() {
        queueList.replaceChildren();
        queue.forEach((track, index) => {
            const item = document.createElement("li");
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = `${track.title} — ${track.artist}`;
            button.setAttribute("aria-current", index === queueIndex ? "true" : "false");
            button.disabled = Boolean(joinedHost);
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
        } else {
            cover.style.backgroundImage = "";
            cover.classList.remove("has-cover");
        }
        player.querySelector("[data-expanded-title]").textContent = track.title || "Без названия";
        player.querySelector("[data-expanded-artist]").textContent = track.artist || "Неизвестный исполнитель";
        const expandedCover = player.querySelector("[data-expanded-cover]");
        expandedCover.style.backgroundImage = track.cover ? `url("${CSS.escape(track.cover)}")` : "";
        const tagList = player.querySelector("[data-expanded-tags]");
        tagList.replaceChildren(...(track.tags || []).map((tag) => {
            const chip = document.createElement("span");
            chip.className = "music-tag-chip";
            chip.textContent = `#${tag}`;
            return chip;
        }));
        seek.disabled = false;
        playerLikeForm.dataset.trackId = track.id;
        playerLikeForm.action = playerLikeUrl.replace(/0\/like\/$/, `${track.id}/like/`);
        playerLikeButton.disabled = false;
        playerLikeButton.classList.toggle("is-liked", Boolean(track.liked));
        playerLikeButton.setAttribute("aria-pressed", String(Boolean(track.liked)));
        playerLikeButton.setAttribute("aria-label", track.liked ? "Убрать из понравившихся" : "Нравится");
        player.querySelector(".music-player-like-count").textContent = track.likeCount || "";
    }

    function setTrack(track, index = -1, shouldPlay = true) {
        if (shouldPlay || audioContext) ensureAudioGraph();
        activeTrack = track;
        queueIndex = index;
        audio.src = track.url;
        audio.load();
        paintTrack(track);
        renderQueue();
        updateListenAlongControls();
        if (shouldPlay) audio.play().catch(() => showToast("Нажмите «Воспроизвести», чтобы начать"));
        saveState();
        sendNowPlaying(!audio.paused);
    }

    function playIndex(index) {
        if (index < 0 || index >= queue.length) return;
        setTrack(queue[index], index, true);
    }

    function stopRadioMode() {
        radioMode = null;
        radioGeneration += 1;
        radioLoading = false;
        radioStartOnLoad = false;
    }

    async function loadRadioTracks(startWhenReady = false) {
        if (!radioMode) return;
        if (startWhenReady) radioStartOnLoad = true;
        if (radioLoading) return;
        radioLoading = true;
        const generation = radioGeneration;
        const currentMode = radioMode;
        try {
            const response = await fetch(currentMode.endpoint, {
                credentials: "same-origin",
                headers: { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest" },
            });
            if (!response.ok) throw new Error("Не удалось загрузить радио");
            const data = await response.json();
            if (generation !== radioGeneration || currentMode !== radioMode) return;
            const queuedIds = new Set(queue.map((track) => String(track.id)));
            const added = (data.tracks || [])
                .filter((track) => !queuedIds.has(String(track.id)))
                .map((track) => ({ ...track, id: String(track.id), playlistId: "" }));
            queue.push(...added);
            renderQueue();
            const status = document.querySelector("[data-radio-status]");
            if (status) status.textContent = added.length
                ? `В очереди треков: ${queue.length - Math.max(0, queueIndex + 1)}`
                : "Новых треков с этим тегом пока нет";
            if (radioStartOnLoad) {
                radioStartOnLoad = false;
                if (queueIndex + 1 < queue.length) {
                    if (joinedHost) leaveListenAlong();
                    playIndex(queueIndex + 1);
                } else if (!added.length) {
                    showToast("Новых треков для радио нет");
                }
            }
        } catch (_) {
            if (generation === radioGeneration) showToast("Не удалось загрузить треки радио");
        } finally {
            if (generation === radioGeneration) radioLoading = false;
        }
    }

    function startRadio(endpoint) {
        ensureAudioGraph();
        stopRadioMode();
        radioMode = { endpoint };
        queue = [];
        queueIndex = -1;
        renderQueue();
        loadRadioTracks(true);
    }

    function updateListenAlongControls() {
        const locked = Boolean(joinedHost);
        toggle.disabled = locked;
        player.querySelector("[data-player-previous]").disabled = locked;
        player.querySelector("[data-player-next]").disabled = locked;
        seek.disabled = locked || !activeTrack;
        player.classList.toggle("is-listening-along", locked);
        renderQueue();
    }

    function showListenAlongNotice(message) {
        const notice = player.querySelector("[data-listen-along-notice]");
        notice.textContent = message;
        notice.hidden = false;
        window.setTimeout(() => { notice.hidden = true; }, 5000);
    }

    function resetListenAlong(message = "") {
        joinedHost = null;
        try { sessionStorage.removeItem("koboki.listen-along.v1"); } catch (_) { /* Ignore storage failures. */ }
        const banner = player.querySelector("[data-listen-along-banner]");
        banner.hidden = true;
        banner.removeAttribute("data-host");
        banner.removeAttribute("data-host-endpoint");
        banner.removeAttribute("data-leave-url");
        updateListenAlongControls();
        if (message) showListenAlongNotice(message);
    }

    async function leaveListenAlong({ beacon = false, message = "" } = {}) {
        const banner = player.querySelector("[data-listen-along-banner]");
        const leaveUrl = joinedHost?.leaveUrl || banner.dataset.leaveUrl;
        const csrf = playerLikeForm.querySelector("[name=csrfmiddlewaretoken]")?.value;
        resetListenAlong(message);
        if (!leaveUrl || !csrf) return;
        if (beacon && navigator.sendBeacon) {
            const formData = new FormData();
            formData.append("csrfmiddlewaretoken", csrf);
            navigator.sendBeacon(leaveUrl, formData);
            return;
        }
        fetch(leaveUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-CSRFToken": csrf, "Accept": "application/json" },
        }).catch(() => {});
    }

    async function synchronizeWithHost() {
        if (!joinedHost || syncInFlight || document.hidden) return;
        syncInFlight = true;
        try {
            const response = await fetch(joinedHost.endpoint, {
                credentials: "same-origin",
                headers: { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest" },
            });
            if (!response.ok) throw new Error("Сеанс недоступен");
            const state = await response.json();
            if (!state.visible || !state.track || !state.audio_url) {
                audio.pause();
                leaveListenAlong({ message: `Сеанс с @${joinedHost.username} завершён` });
                return;
            }
            if (!activeTrack || String(activeTrack.id) !== String(state.track_id)) {
                const hostTrack = {
                    id: String(state.track_id),
                    url: state.audio_url,
                    title: state.track.title,
                    artist: state.track.artist,
                    cover: state.cover_url || "",
                    playlistId: state.playlist_id ? String(state.playlist_id) : "",
                    liked: false,
                    likeCount: 0,
                };
                queue = [hostTrack];
                setTrack(hostTrack, 0, false);
            }
            const drift = Math.abs(audio.currentTime - Number(state.position_seconds || 0));
            if (drift > 2) audio.currentTime = Number(state.position_seconds || 0);
            if (state.is_playing && audio.paused) audio.play().catch(() => {});
            if (!state.is_playing && !audio.paused) audio.pause();
            player.querySelectorAll("[data-host-listener-count]").forEach((counter) => {
                counter.textContent = `С вами слушают: ${state.listener_count || 0}`;
                counter.hidden = false;
            });
        } catch (_) {
            leaveListenAlong({ message: "Не удалось продолжить совместное прослушивание" });
        } finally {
            syncInFlight = false;
        }
    }

    async function joinListenAlong(form) {
        ensureAudioGraph();
        const playRequest = audio.play();
        if (playRequest && typeof playRequest.catch === "function") playRequest.catch(() => {});
        const csrf = form.querySelector("[name=csrfmiddlewaretoken]")?.value;
        if (!csrf) {
            form.submit();
            return;
        }
        try {
            const response = await fetch(form.action, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "X-CSRFToken": csrf,
                    "X-Requested-With": "XMLHttpRequest",
                },
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "Не удалось подключиться");
            joinedHost = {
                username: result.host,
                endpoint: result.endpoint,
                leaveUrl: result.leave_url,
            };
            try { sessionStorage.setItem("koboki.listen-along.v1", JSON.stringify(joinedHost)); } catch (_) { /* Ignore storage failures. */ }
            const banner = player.querySelector("[data-listen-along-banner]");
            banner.dataset.host = joinedHost.username;
            banner.dataset.hostEndpoint = joinedHost.endpoint;
            banner.dataset.leaveUrl = joinedHost.leaveUrl;
            player.querySelector("[data-listen-along-host]").textContent = `@${joinedHost.username}`;
            banner.hidden = false;
            updateListenAlongControls();
            await synchronizeWithHost();
            if (playRequest && typeof playRequest.catch === "function") playRequest.catch(() => {});
        } catch (error) {
            if (playRequest && typeof playRequest.catch === "function") playRequest.catch(() => {});
            showListenAlongNotice(error.message || "Не удалось подключиться к сеансу");
        }
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
            tags: (button.dataset.trackTags || "").split("|").filter(Boolean),
        };
    }

    function playFromButton(button) {
        stopRadioMode();
        if (joinedHost) leaveListenAlong();
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
            if (audio.paused) { ensureAudioGraph(); audio.play().catch(() => {}); }
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
        } else if (button.matches("[data-player-expand]")) {
            setExpanded(!expanded);
        } else if (button.matches("[data-player-close]")) {
            setExpanded(false);
        } else if (button.matches("[data-player-native-fullscreen]")) {
            if (!document.fullscreenElement) player.requestFullscreen?.().catch(() => showToast("Полноэкранный режим недоступен"));
            else document.exitFullscreen?.();
        } else if (button.matches("[data-sound-toggle]")) {
            const panel = player.querySelector("[data-sound-panel]");
            panel.hidden = !panel.hidden;
            button.setAttribute("aria-expanded", String(!panel.hidden));
            if (!panel.hidden) ensureAudioGraph();
        }
    });

    document.addEventListener("click", (event) => {
        const radioButton = event.target.closest("[data-radio-start]");
        if (radioButton) {
            const page = radioButton.closest("[data-music-radio]");
            if (page?.dataset.radioEndpoint) startRadio(page.dataset.radioEndpoint);
            return;
        }
        const enqueueButton = event.target.closest("[data-enqueue-track]");
        if (enqueueButton) {
            const row = enqueueButton.closest("[data-track-id]");
            const playButton = row?.querySelector("[data-track-play]");
            if (playButton) {
                const track = trackFromButton(playButton);
                if (!queue.some((item) => item.id === track.id)) {
                    queue.push(track);
                    renderQueue();
                    saveState();
                }
                showToast("Трек добавлен в очередь");
            }
            closeTrackMenu(enqueueButton);
            return;
        }
        const copyButton = event.target.closest("[data-copy-track-link]");
        if (copyButton) {
            const url = new URL(copyButton.dataset.trackUrl, location.origin).href;
            if (navigator.clipboard?.writeText) {
                navigator.clipboard.writeText(url).then(
                    () => showToast("Ссылка скопирована"),
                    () => showToast("Не удалось скопировать ссылку"),
                );
            } else {
                showToast("Копирование недоступно в этом браузере");
            }
            closeTrackMenu(copyButton);
            return;
        }
        const playlistButton = event.target.closest("[data-play-playlist]");
        if (playlistButton) {
            stopRadioMode();
            if (joinedHost) leaveListenAlong();
            const playlistId = playlistButton.dataset.playlistId;
            const list = document.querySelector(`[data-playlist-track-list="${CSS.escape(playlistId)}"]`);
            if (!list) return;
            queue = Array.from(list.querySelectorAll("[data-track-play]"), (button) => {
                const track = trackFromButton(button);
                track.playlistId = playlistId.startsWith("shared-") ? "" : playlistId;
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
        const joinForm = event.target.closest("[data-listen-along-join]");
        if (joinForm) {
            event.preventDefault();
            joinListenAlong(joinForm);
            return;
        }
        const leaveForm = event.target.closest("[data-listen-along-leave]");
        if (leaveForm) {
            event.preventDefault();
            leaveListenAlong();
            return;
        }
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
            const nextSideNav = nextDocument.querySelector(".side-nav");
            const currentSideNav = document.querySelector(".side-nav");
            if (!nextMain || !currentMain || !nextSideNav || !currentSideNav) {
                throw new Error("Page layout not found");
            }
            currentMain.innerHTML = nextMain.innerHTML;
            currentSideNav.innerHTML = nextSideNav.innerHTML;
            document.body.classList.toggle(
                "music-page",
                nextDocument.body.classList.contains("music-page"),
            );
            document.title = nextDocument.title;
            if (push) history.pushState({}, "", url);
            window.scrollTo(0, 0);
        } catch (_) {
            location.assign(url);
        }
    }

    window.addEventListener("popstate", () => navigate(location.href, false));
    audio.addEventListener("play", () => { toggle.classList.add("is-playing"); toggle.setAttribute("aria-label", "Пауза"); saveState(); sendNowPlaying(true); });
    audio.addEventListener("pause", () => { toggle.classList.remove("is-playing"); toggle.setAttribute("aria-label", "Воспроизвести"); saveState(); sendNowPlaying(false); });
    audio.addEventListener("seeked", () => sendNowPlaying(!audio.paused));
    audio.addEventListener("timeupdate", () => {
        currentTime.textContent = formatTime(audio.currentTime);
        duration.textContent = formatTime(audio.duration);
        if (Number.isFinite(audio.duration) && audio.duration > 0) seek.value = String(Math.round(audio.currentTime / audio.duration * 1000));
        saveState();
        if (radioMode && queue.length - queueIndex <= 3) loadRadioTracks();
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
    audio.addEventListener("ended", () => {
        if (queueIndex + 1 < queue.length) playIndex(queueIndex + 1);
        else if (radioMode) loadRadioTracks(true);
    });
    seek.addEventListener("input", () => {
        if (Number.isFinite(audio.duration)) audio.currentTime = Number(seek.value) / 1000 * audio.duration;
    });
    seek.addEventListener("change", saveState);
    player.querySelector("[data-player-volume]").addEventListener("input", (event) => {
        audio.volume = Number(event.target.value);
        saveState();
    });
    player.querySelector("[data-eq-enabled]").addEventListener("change", () => { ensureAudioGraph(); applySoundSettings(); saveSoundSettings(); });
    player.querySelectorAll("[data-eq-band]").forEach((input) => input.addEventListener("input", () => {
        ensureAudioGraph(); soundControls().eqPreset.value = "custom"; applySoundSettings(); saveSoundSettings();
    }));
    player.querySelector("[data-eq-preset]").addEventListener("change", (event) => setEqualizerPreset(event.target.value));
    player.querySelectorAll("[data-compressor]").forEach((input) => input.addEventListener("input", () => {
        ensureAudioGraph(); soundControls().compressorPreset.value = "custom"; applySoundSettings(); saveSoundSettings();
    }));
    player.querySelector("[data-compressor-preset]").addEventListener("change", (event) => setCompressorPreset(event.target.value));
    player.querySelector("[data-eq-reset]").addEventListener("click", () => setEqualizerPreset("flat"));
    document.addEventListener("keydown", (event) => {
        const target = event.target;
        if (event.key === "Escape" && expanded) {
            event.preventDefault();
            setExpanded(false);
            return;
        }
        if (expanded && event.key === "Tab") {
            const focusable = [...player.querySelectorAll("button:not([disabled]):not([hidden]), input:not([disabled]), select:not([disabled]), a[href]")].filter((element) => element.getClientRects().length);
            if (!focusable.length) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
        if (target.matches("input, textarea, select, button, summary, [contenteditable='true']")) return;
        if (event.code === "Space") {
            event.preventDefault();
            if (!activeTrack || joinedHost) return;
            if (audio.paused) { ensureAudioGraph(); audio.play().catch(() => {}); }
            else audio.pause();
        } else if (event.code === "ArrowLeft" || event.code === "ArrowRight") {
            if (!activeTrack || joinedHost) return;
            event.preventDefault();
            audio.currentTime = Math.max(0, Math.min(audio.duration || Infinity, audio.currentTime + (event.code === "ArrowRight" ? 5 : -5)));
        } else if (event.code === "ArrowUp" || event.code === "ArrowDown") {
            event.preventDefault();
            audio.volume = Math.max(0, Math.min(1, audio.volume + (event.code === "ArrowUp" ? 0.05 : -0.05)));
            player.querySelector("[data-player-volume]").value = String(audio.volume);
            saveState();
        } else if (event.key.toLowerCase() === "m") {
            audio.muted = !audio.muted;
            showToast(audio.muted ? "Звук выключен" : "Звук включён");
        } else if (event.key.toLowerCase() === "f") {
            setExpanded(!expanded);
        }
    });
    window.addEventListener("beforeunload", () => {
        sendNowPlaying(false, true);
        if (joinedHost) leaveListenAlong({ beacon: true });
    });
    window.setInterval(() => {
        if (activeTrack) sendNowPlaying(!audio.paused);
    }, 5000);

    function updateNowPlayingCard(card, data) {
        const status = card.querySelector("[data-now-status]");
        const details = card.querySelector("[data-now-details]");
        const indicator = card.querySelector("[data-now-indicator]");
        if (!data.visible) {
            status.textContent = "Пользователь скрыл эту информацию.";
            if (details) details.hidden = true;
            indicator.classList.remove("is-playing");
            return;
        }
        if (!data.track) {
            if (details) details.hidden = true;
            status.textContent = data.last_seen_minutes
                ? `Был(а) в сети ${data.last_seen_minutes} мин. назад`
                : "Сейчас не слушает";
            indicator.classList.remove("is-playing");
            return;
        }
        details.hidden = false;
        card.querySelector("[data-now-title]").textContent = data.track.title;
        card.querySelector("[data-now-artist]").textContent = data.track.artist;
        const source = card.querySelector("[data-now-source]");
        source.replaceChildren();
        if (data.source?.url) {
            const link = document.createElement("a");
            link.href = data.source.url;
            link.textContent = data.source.label;
            source.append(link);
        } else {
            source.textContent = data.source?.label || "из библиотеки";
        }
        card.dataset.position = String(data.position_seconds || 0);
        card.dataset.duration = String(data.duration_seconds || 0);
        card.dataset.playing = String(Boolean(data.is_playing));
        card.dataset.syncedAt = String(Date.now());
        status.textContent = data.is_playing ? "Слушает сейчас" : "Пауза";
        indicator.classList.toggle("is-playing", Boolean(data.is_playing));
        const listenerCount = card.querySelector("[data-host-listener-count]");
        if (listenerCount) listenerCount.textContent = `С вами слушают: ${data.listener_count || 0}`;
        renderNowPlayingProgress(card);
    }

    function renderNowPlayingProgress(card) {
        if (card.querySelector("[data-now-details]")?.hidden) return;
        const durationValue = Number(card.dataset.duration || 0);
        const elapsed = card.dataset.playing === "true"
            ? (Date.now() - Number(card.dataset.syncedAt || Date.now())) / 1000
            : 0;
        const position = Math.min(durationValue || Infinity, Number(card.dataset.position || 0) + elapsed);
        card.querySelector("[data-now-current]").textContent = formatTime(position);
        card.querySelector("[data-now-duration]").textContent = formatTime(durationValue);
        const percent = durationValue ? Math.min(100, position / durationValue * 100) : 0;
        card.querySelector("[data-now-progress]").style.width = `${percent}%`;
    }

    async function pollNowPlayingCards() {
        if (document.hidden) return;
        for (const card of document.querySelectorAll("[data-now-playing-card]")) {
            try {
                const response = await fetch(card.dataset.endpoint, {
                    credentials: "same-origin",
                    headers: { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest" },
                });
                if (response.ok) updateNowPlayingCard(card, await response.json());
            } catch (_) { /* Keep the last rendered snapshot while offline. */ }
        }
    }

    window.setInterval(() => {
        document.querySelectorAll("[data-now-playing-card]").forEach(renderNowPlayingProgress);
    }, 1000);
    window.setInterval(pollNowPlayingCards, 5000);
    window.setInterval(synchronizeWithHost, 3000);
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            pollNowPlayingCards();
            synchronizeWithHost();
        }
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

    if (!listenBanner.hidden && listenBanner.dataset.host) {
        joinedHost = {
            username: listenBanner.dataset.host,
            endpoint: listenBanner.dataset.hostEndpoint,
            leaveUrl: listenBanner.dataset.leaveUrl,
        };
        updateListenAlongControls();
        synchronizeWithHost();
    }
})();
