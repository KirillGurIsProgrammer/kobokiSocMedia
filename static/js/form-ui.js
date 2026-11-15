document.addEventListener("DOMContentLoaded", () => {
    const input = document.querySelector(".track-form input[type='file']");
    const picker = input?.closest(".file-picker");
    const fileName = picker?.querySelector("[data-file-name]");

    if (!input || !picker || !fileName) return;

    const list = document.querySelector("[data-track-upload-list]");
    if (!input.multiple || !list) {
        input.addEventListener("change", () => {
            const file = input.files?.[0];
            fileName.textContent = file?.name || "Файл не выбран";
            picker.classList.toggle("has-file", Boolean(file));
        });
        return;
    }

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
        if (listId) field.setAttribute("list", listId);
        label.append(field);
        container.append(label);
    }

    input.addEventListener("change", () => {
        const files = Array.from(input.files || []);
        fileName.textContent = files.length
            ? `Выбрано файлов: ${files.length}`
            : "Файлы не выбраны";
        picker.classList.toggle("has-file", files.length > 0);
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
            row.append(heading, fields);
            list.append(row);
        });
    });
});
