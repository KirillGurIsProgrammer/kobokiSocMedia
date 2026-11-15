(() => {
    function parseFilename(filename) {
        let stem = filename.replace(/\.[^.]+$/, "").replace(/_/g, " ");
        stem = stem.replace(/\s*[([{][^\])}]*?(?:official\s+video|(?:\d+\s*)?kbps)[^\])}]*[)\]}]/gi, " ");
        stem = stem.replace(/(?:https?:\/\/|www\.)\S+|\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:\/\S*)?/gi, " ");
        stem = stem.replace(/^\s*\d+\s*(?:[.\-–—]\s*|\s+)/, "");
        stem = stem.replace(/\s+/g, " ").trim();
        const separator = stem.match(/\s[-–—]\s/);
        if (!separator) return { artist: "", title: stem };
        const position = separator.index;
        return {
            artist: stem.slice(0, position).trim(),
            title: stem.slice(position + separator[0].length).trim(),
        };
    }

    function addField(container, labelText, name, value, index, listId = "") {
        const label = document.createElement("label");
        label.className = "track-upload-field";
        label.append(document.createTextNode(labelText));

        const field = document.createElement("input");
        field.type = "text";
        field.name = `${name}_${index}`;
        field.value = value;
        field.autocomplete = "off";
        field.className = "input";
        if (listId) field.setAttribute("list", listId);
        label.append(field);
        container.append(label);
    }

    function initializeFileInputs() {
        document.querySelectorAll(".track-form input[type='file']").forEach((input) => {
            const picker = input.closest(".file-picker");
            const fileName = picker?.querySelector("[data-file-name]");
            if (!fileName) return;
            const files = Array.from(input.files || []);
            if (files.length) {
                fileName.textContent = input.multiple ? `Выбрано файлов: ${files.length}` : files[0].name;
                picker.classList.add("has-file");
            }
        });
    }

    document.addEventListener("change", (event) => {
        const input = event.target.closest(".track-form input[type='file']");
        if (!input) return;
        const picker = input.closest(".file-picker");
        const fileName = picker?.querySelector("[data-file-name]");
        if (!picker || !fileName) return;

        const files = Array.from(input.files || []);
        const list = input.closest("form")?.querySelector("[data-track-upload-list]");
        picker.classList.toggle("has-file", files.length > 0);
        if (!input.multiple || !list) {
            fileName.textContent = files[0]?.name || "Файл не выбран";
            return;
        }

        fileName.textContent = files.length ? `Выбрано файлов: ${files.length}` : "Файлы не выбраны";
        list.replaceChildren();
        list.hidden = files.length === 0;
        files.forEach((file, index) => {
            const parsed = parseFilename(file.name);
            const row = document.createElement("section");
            row.className = "track-upload-row";

            const heading = document.createElement("h2");
            heading.className = "track-upload-filename";
            heading.textContent = file.name;

            const fields = document.createElement("div");
            fields.className = "track-upload-fields";
            addField(fields, "Название", "title", parsed.title, index);
            addField(fields, "Исполнитель", "artist", parsed.artist, index);
            addField(fields, "Теги", "tags", "", index, "music-tag-suggestions");
            const coverLabel = document.createElement("label");
            coverLabel.className = "track-upload-field track-upload-cover";
            coverLabel.append(document.createTextNode("Обложка трека"));
            const coverInput = document.createElement("input");
            coverInput.type = "file";
            coverInput.name = `cover_${index}`;
            coverInput.accept = ".jpg,.jpeg,.png,.webp";
            coverInput.className = "input";
            coverLabel.append(coverInput);
            fields.append(coverLabel);
            row.append(heading, fields);
            list.append(row);
        });
    });

    document.addEventListener("kobokiPageLoaded", initializeFileInputs);
    initializeFileInputs();
})();
