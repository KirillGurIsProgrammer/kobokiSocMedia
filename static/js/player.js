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
    const playerLikeForms = [...player.querySelectorAll("[data-player-like-form]")];
    const playerLikeUrl = playerLikeForms[0].action;
    const playerLikeButtons = [...player.querySelectorAll("[data-player-like]")];
    const volumeInput = player.querySelector("[data-player-volume]");
    const trackUrlTemplate = player.dataset.trackUrlTemplate;
    const artistUrlTemplate = player.dataset.artistUrlTemplate;
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
    let expansionTimer = 0;
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
        if (value === expanded) return;
        window.clearTimeout(expansionTimer);
        expanded = value;
        player.querySelectorAll("[data-player-expand]").forEach((button) => button.setAttribute("aria-pressed", String(expanded)));
        if (expanded) {
            player.classList.remove("is-closing");
            player.classList.add("is-expanded");
            document.body.classList.add("player-expanded");
            player.setAttribute("role", "dialog");
            player.setAttribute("aria-modal", "true");
            player.querySelector("[data-player-close]").hidden = false;
            previousFocus = document.activeElement;
            player.querySelector("[data-player-close]").focus();
        } else {
            player.classList.add("is-closing");
            const finishClosing = () => {
                player.classList.remove("is-expanded", "is-closing");
                document.body.classList.remove("player-expanded");
                player.setAttribute("role", "region");
                player.removeAttribute("aria-modal");
                player.querySelector("[data-player-close]").hidden = true;
                previousFocus?.focus?.();
                previousFocus = null;
            };
            const duration = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 220;
            if (duration) expansionTimer = window.setTimeout(finishClosing, duration);
            else finishClosing();
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
        try {
            localStorage.setItem(storageKey, JSON.stringify({
                track: activeTrack,
                queue,
                queueIndex,
                position: activeTrack ? (audio.currentTime || 0) : 0,
                volume: audio.volume,
                mode: radioMode ? { endpoint: radioMode.endpoint } : null,
                wasPlaying: false,
            }));
        } catch (_) { /* Storage can be unavailable in private browsing. */ }
    }

    function dispatchPlayerChange() {
        const detail = {
            track: activeTrack ? { ...activeTrack } : null,
            isPlaying: !audio.paused,
            position: audio.currentTime || 0,
            duration: Number.isFinite(audio.duration) ? audio.duration : 0,
            queue: queue.map((track) => ({ ...track })),
        };
        window.dispatchEvent(new CustomEvent("player:change", { detail }));
        document.dispatchEvent(new CustomEvent("player:change", { detail }));
    }

    function sendNowPlaying(isPlaying = !audio.paused, beacon = false) {
        if (!activeTrack?.id || !nowPlayingUrl) return;
        const csrf = playerLikeForms[0].querySelector("[name=csrfmiddlewaretoken]")?.value;
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
        queueToggle.disabled = !queue.length || Boolean(joinedHost);
        player.querySelectorAll("[data-player-previous]").forEach((button) => {
            button.disabled = Boolean(joinedHost) || !activeTrack || (queueIndex <= 0 && audio.currentTime <= 3);
        });
        player.querySelectorAll("[data-player-next]").forEach((button) => {
            button.disabled = Boolean(joinedHost) || !activeTrack || queueIndex + 1 >= queue.length;
        });
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

    function pageUrlForTrack(id) {
        return trackUrlTemplate?.replace(/0\/?$/, `${encodeURIComponent(id)}/`) || "";
    }

    function pageUrlForArtist(username) {
        return username && artistUrlTemplate
            ? artistUrlTemplate.replace("__username__", encodeURIComponent(username))
            : "";
    }

    function setLinkedText(element, text, url) {
        element.textContent = text || "";
        if (url) {
            element.href = url;
            element.removeAttribute("aria-disabled");
        } else {
            element.removeAttribute("href");
            element.setAttribute("aria-disabled", "true");
        }
    }

    function paintRange(input) {
        const min = Number(input.min || 0);
        const max = Number(input.max || 100);
        const value = Number(input.value || 0);
        const percent = max > min ? ((value - min) / (max - min)) * 100 : 0;
        input.style.setProperty("--range-progress", `${Math.max(0, Math.min(100, percent))}%`);
    }

    audio.volume = Number(volumeInput.value);
    paintRange(volumeInput);

    function markPlayingTrack(id) {
        document.querySelectorAll("[data-track-row]").forEach((row) => {
            row.classList.toggle("is-playing", Boolean(id) && row.dataset.trackId === String(id));
        });
    }

    function syncMediaSession() {
        const mediaSession = navigator.mediaSession;
        if (!mediaSession) return;
        if (!activeTrack) {
            mediaSession.metadata = null;
            mediaSession.playbackState = "none";
            return;
        }
        if ("MediaMetadata" in window) {
            mediaSession.metadata = new MediaMetadata({
                title: activeTrack.title || "Без названия",
                artist: activeTrack.artist || "Неизвестный исполнитель",
                artwork: activeTrack.cover ? [{ src: activeTrack.cover }] : [],
            });
        }
        mediaSession.playbackState = audio.paused ? "paused" : "playing";
        if (Number.isFinite(audio.duration) && audio.duration > 0 && mediaSession.setPositionState) {
            try {
                mediaSession.setPositionState({
                    duration: audio.duration,
                    playbackRate: audio.playbackRate || 1,
                    position: Math.min(audio.currentTime || 0, audio.duration),
                });
            } catch (_) { /* Ignore invalid media position reports. */ }
        }
    }

    function paintTrack(track) {
        const artistName = track.artist || "Неизвестный исполнитель";
        const trackPageUrl = track.trackPageUrl || pageUrlForTrack(track.id);
        const artistPageUrl = track.artistPageUrl || pageUrlForArtist(track.artistUsername || joinedHost?.username);
        setLinkedText(title, track.title || "Без названия", trackPageUrl);
        setLinkedText(artist, artistName, artistPageUrl);
        if (track.cover) {
            cover.style.backgroundImage = `url("${CSS.escape(track.cover)}")`;
            cover.classList.add("has-cover");
        } else {
            cover.style.backgroundImage = "";
            cover.classList.remove("has-cover");
        }
        const expandedTitle = player.querySelector("[data-expanded-title]");
        const expandedArtist = player.querySelector("[data-expanded-artist]");
        setLinkedText(expandedTitle, track.title || "Без названия", trackPageUrl);
        setLinkedText(expandedArtist, artistName, artistPageUrl);
        const expandedCover = player.querySelector("[data-expanded-cover]");
        expandedCover.style.backgroundImage = track.cover ? `url("${CSS.escape(track.cover)}")` : "";
        expandedCover.classList.toggle("has-cover", Boolean(track.cover));
        const tagList = player.querySelector("[data-expanded-tags]");
        tagList.replaceChildren(...(track.tags || []).map((tag) => {
            const chip = document.createElement("span");
            chip.className = "music-tag-chip";
            chip.textContent = `#${tag}`;
            return chip;
        }));
        playerLikeForms.forEach((form) => {
            form.dataset.trackId = track.id;
            form.action = playerLikeUrl.replace(/0\/like\/$/, `${track.id}/like/`);
        });
        playerLikeButtons.forEach((button) => {
            button.disabled = false;
            button.classList.toggle("is-liked", Boolean(track.liked));
            button.setAttribute("aria-pressed", String(Boolean(track.liked)));
            button.setAttribute("aria-label", track.liked ? "Убрать из понравившихся" : "Нравится");
            button.setAttribute("title", track.liked ? "Убрать из понравившихся" : "Нравится");
        });
        player.querySelectorAll("[data-player-expand]").forEach((button) => { button.disabled = false; });
        player.querySelectorAll("[data-sound-toggle]").forEach((button) => { button.disabled = false; });
        seek.disabled = Boolean(joinedHost);
        toggle.disabled = Boolean(joinedHost);
        paintRange(seek);
        markPlayingTrack(track.id);
        syncMediaSession();
        dispatchPlayerChange();
    }

    function setTrack(track, index = -1, shouldPlay = true) {
        if (shouldPlay) restoring = false;
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

    function playTrack(track) {
        if (!track?.url || !track.id) return;
        stopRadioMode();
        if (joinedHost) leaveListenAlong();
        track = { ...track, id: String(track.id) };
        const index = queue.findIndex((queuedTrack) => String(queuedTrack.id) === track.id);
        if (index >= 0) {
            queue[index] = { ...queue[index], ...track };
            playIndex(index);
        } else {
            queue = [track];
            playIndex(0);
        }
    }

    function enqueueTrack(track) {
        if (!track?.url || !track.id) return;
        const normalized = { ...track, id: String(track.id) };
        if (queue.some((queuedTrack) => String(queuedTrack.id) === normalized.id)) return;
        queue.push(normalized);
        renderQueue();
        saveState();
        dispatchPlayerChange();
    }

    window.KobokiPlayer = {
        play: playTrack,
        pause: () => audio.pause(),
        next: () => playIndex(queueIndex + 1),
        prev: () => audio.currentTime > 3 ? (audio.currentTime = 0) : playIndex(queueIndex - 1),
        enqueue: enqueueTrack,
        getState: () => ({
            track: activeTrack ? { ...activeTrack } : null,
            isPlaying: !audio.paused,
            position: audio.currentTime || 0,
            volume: audio.volume,
            queue: queue.map((track) => ({ ...track })),
        }),
    };

    ["play", "pause", "nexttrack", "previoustrack"].forEach((action) => {
        try {
            navigator.mediaSession?.setActionHandler(action, () => {
                if (action === "play") {
                    if (!activeTrack) return;
                    restoring = false;
                    ensureAudioGraph();
                    audio.play().catch(() => {});
                } else if (action === "pause") {
                    audio.pause();
                } else if (action === "nexttrack") {
                    window.KobokiPlayer.next();
                } else {
                    window.KobokiPlayer.prev();
                }
            });
        } catch (_) { /* Some browsers expose only part of Media Session. */ }
    });

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
        const hasTrack = Boolean(activeTrack);
        toggle.disabled = locked || !hasTrack;
        player.querySelectorAll("[data-player-previous]").forEach((button) => { button.disabled = locked || !hasTrack || (queueIndex <= 0 && audio.currentTime <= 3); });
        player.querySelectorAll("[data-player-next]").forEach((button) => { button.disabled = locked || !hasTrack || queueIndex + 1 >= queue.length; });
        player.querySelectorAll("[data-player-expand]").forEach((button) => { button.disabled = !hasTrack; });
        player.querySelectorAll("[data-player-like]").forEach((button) => { button.disabled = !hasTrack; });
        player.querySelectorAll("[data-sound-toggle]").forEach((button) => { button.disabled = !hasTrack; });
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
        const csrf = playerLikeForms[0].querySelector("[name=csrfmiddlewaretoken]")?.value;
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
        const trackId = button.dataset.trackId || button.dataset.playTrack;
        return {
            id: trackId,
            url: button.dataset.trackUrl,
            trackPageUrl: button.dataset.trackPageUrl || pageUrlForTrack(trackId),
            artistPageUrl: button.dataset.trackArtistUrl || "",
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
        queue = list ? Array.from(list.querySelectorAll("[data-track-play], [data-play-track]"), trackFromButton) : [trackFromButton(button)];
        window.KobokiPlayer.play(trackFromButton(button));
    }

    player.addEventListener("click", (event) => {
        const button = event.target.closest("button");
        if (!button) {
            if (!expanded && activeTrack && (event.target === player || event.target.closest(".music-player-track"))) {
                if (!event.target.closest("a")) setExpanded(true);
            }
            return;
        }
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
        } else if (button.matches("[data-queue-close]")) {
            queuePanel.hidden = true;
            queueToggle.setAttribute("aria-expanded", "false");
        } else if (button.matches("[data-player-expand]")) {
            setExpanded(!expanded);
        } else if (button.matches("[data-player-close]")) {
            setExpanded(false);
        } else if (button.matches("[data-sound-toggle]")) {
            const panel = player.querySelector("[data-sound-panel]");
            panel.hidden = !panel.hidden;
            button.setAttribute("aria-expanded", String(!panel.hidden));
            if (!panel.hidden) ensureAudioGraph();
        }
    });

    document.addEventListener("click", (event) => {
        if (!event.target.closest(".music-track-menu, .track-detail-menu")) {
            document.querySelectorAll(".music-track-menu[open], .track-detail-menu[open]").forEach((menu) => { menu.open = false; });
        }
        if (!event.target.closest(".music-queue, [data-queue-toggle]") && !queuePanel.hidden) {
            queuePanel.hidden = true;
            queueToggle.setAttribute("aria-expanded", "false");
        }
        const radioButton = event.target.closest("[data-radio-start]");
        if (radioButton) {
            const page = radioButton.closest("[data-music-radio]");
            if (page?.dataset.radioEndpoint) startRadio(page.dataset.radioEndpoint);
            return;
        }
        const enqueueButton = event.target.closest("[data-enqueue-track]");
        if (enqueueButton) {
            const row = enqueueButton.closest("[data-track-id]");
            const playButton = row?.querySelector("[data-track-play], [data-play-track]");
            if (playButton) {
                const track = trackFromButton(playButton);
                const alreadyQueued = queue.some((item) => String(item.id) === String(track.id));
                window.KobokiPlayer.enqueue(track);
                showToast(alreadyQueued ? "Трек уже в очереди" : "Трек добавлен в очередь");
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
        const playButton = event.target.closest("[data-track-play], [data-play-track]");
        if (playButton) {
            event.preventDefault();
            playFromButton(playButton);
            return;
        }
        const trackRow = event.target.closest("[data-track-row]");
        if (trackRow && !event.target.closest("a, button, details, form, input, select, textarea")) {
            const rowPlayButton = trackRow.querySelector("[data-track-play], [data-play-track]");
            if (rowPlayButton) playFromButton(rowPlayButton);
            return;
        }
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
                button.setAttribute("title", result.liked ? "Убрать из понравившихся" : "Нравится");
                const label = likeForm.querySelector("[data-like-label]");
                if (label) label.textContent = result.liked ? "Убрать лайк" : "Нравится";
                const count = likeForm.querySelector("[data-like-count]");
                if (count) count.textContent = result.like_count;
            });
            document.querySelectorAll("[data-track-row]").forEach((row) => {
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
            closeTrackMenu(form);
        } catch (_) {
            form.submit();
        }
    });

    audio.addEventListener("play", () => {
        restoring = false;
        toggle.classList.add("is-playing");
        toggle.setAttribute("aria-label", "Пауза");
        toggle.setAttribute("title", "Пауза");
        saveState();
        syncMediaSession();
        dispatchPlayerChange();
        sendNowPlaying(true);
    });
    audio.addEventListener("pause", () => {
        toggle.classList.remove("is-playing");
        toggle.setAttribute("aria-label", "Воспроизвести");
        toggle.setAttribute("title", "Воспроизвести");
        saveState();
        syncMediaSession();
        dispatchPlayerChange();
        sendNowPlaying(false);
    });
    audio.addEventListener("seeked", () => sendNowPlaying(!audio.paused));
    audio.addEventListener("timeupdate", () => {
        currentTime.textContent = formatTime(audio.currentTime);
        duration.textContent = formatTime(audio.duration);
        if (Number.isFinite(audio.duration) && audio.duration > 0) seek.value = String(Math.round(audio.currentTime / audio.duration * 1000));
        paintRange(seek);
        updateListenAlongControls();
        saveState();
        if (radioMode && queue.length - queueIndex <= 3) loadRadioTracks();
    });
    audio.addEventListener("loadedmetadata", () => {
        duration.textContent = formatTime(audio.duration);
        paintRange(seek);
        updateListenAlongControls();
        if (restoring && activeTrack) {
            const state = restoring;
            audio.currentTime = Math.min(state.position || 0, audio.duration || 0);
            restoring = false;
            audio.pause();
            saveState();
        }
        syncMediaSession();
    });
    audio.addEventListener("ended", () => {
        if (queueIndex + 1 < queue.length) playIndex(queueIndex + 1);
        else if (radioMode) loadRadioTracks(true);
    });
    seek.addEventListener("input", () => {
        if (Number.isFinite(audio.duration)) audio.currentTime = Number(seek.value) / 1000 * audio.duration;
        paintRange(seek);
    });
    seek.addEventListener("change", saveState);
    volumeInput.addEventListener("input", (event) => {
        audio.volume = Number(event.target.value);
        paintRange(event.target);
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
        if (event.key === "Escape") {
            const openMenu = document.querySelector(".music-track-menu[open], .track-detail-menu[open]");
            if (openMenu) {
                openMenu.open = false;
                openMenu.querySelector("summary")?.focus();
                return;
            }
            if (!queuePanel.hidden) {
                queuePanel.hidden = true;
                queueToggle.setAttribute("aria-expanded", "false");
                queueToggle.focus();
                return;
            }
        }
        if (expanded && event.key === "Tab") {
            const focusable = [...player.querySelectorAll("button:not([disabled]):not([hidden]), input:not([disabled]), select:not([disabled]), a[href]")].filter((element) => element.getClientRects().length);
            if (!focusable.length) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
        if (target.matches("input, textarea, select, [contenteditable='true']")) return;
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
            volumeInput.value = String(audio.volume);
            paintRange(volumeInput);
            saveState();
        } else if (event.key.toLowerCase() === "m") {
            audio.muted = !audio.muted;
            showToast(audio.muted ? "Звук выключен" : "Звук включён");
        } else if (event.key.toLowerCase() === "f") {
            setExpanded(!expanded);
        }
    });
    window.addEventListener("beforeunload", () => {
        saveState();
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

    document.addEventListener("kobokiBeforePageChange", () => {
        if (expanded) setExpanded(false);
        queuePanel.hidden = true;
        queueToggle.setAttribute("aria-expanded", "false");
        player.querySelector("[data-sound-panel]").hidden = true;
        player.querySelector("[data-sound-toggle]").setAttribute("aria-expanded", "false");
        document.querySelectorAll(".music-track-menu[open], .track-detail-menu[open]").forEach((menu) => { menu.open = false; });
    });
    document.addEventListener("kobokiPageLoaded", () => markPlayingTrack(activeTrack?.id));

    try {
        const state = JSON.parse(localStorage.getItem(storageKey) || "null");
        if (Number.isFinite(state?.volume)) audio.volume = Math.max(0, Math.min(1, state.volume));
        if (state?.mode?.endpoint) radioMode = { endpoint: state.mode.endpoint };
        if (state?.track?.url) {
            queue = Array.isArray(state.queue) ? state.queue : [state.track];
            queueIndex = Number.isInteger(state.queueIndex) ? state.queueIndex : 0;
            restoring = { ...state, wasPlaying: false };
            setTrack(state.track, queueIndex, false);
        }
    } catch (_) { /* Ignore malformed or unavailable session state. */ }
    volumeInput.value = String(audio.volume);
    paintRange(volumeInput);
    renderQueue();

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
