// CodeDefect AI Client Interactivity

document.addEventListener("DOMContentLoaded", function () {
    // 1. Sidebar Toggle on Mobile
    const sidebarToggle = document.getElementById("sidebarToggle");
    const sidebar = document.getElementById("sidebar-wrapper");

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener("click", function (e) {
            e.preventDefault();
            sidebar.classList.toggle("show");
        });
    }

    // 2. Preset Loader for Direct Defect Prediction Page
    const presetSelect = document.getElementById("dataset_preset");
    if (presetSelect) {
        presetSelect.addEventListener("change", function () {
            const presetId = this.value;
            if (presetId && presetId !== "custom") {
                fetch(`/prediction/api/preset/${presetId}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success && data.preset) {
                            const p = data.preset;
                            // Set language if present
                            const langSelect = document.getElementById("language");
                            if (langSelect && p.language) {
                                langSelect.value = p.language;
                            }
                            // Fill all 21 NASA metric input fields
                            for (const [key, val] of Object.entries(p.metrics)) {
                                const inputField = document.getElementById(key);
                                if (inputField) {
                                    inputField.value = val;
                                }
                            }
                        }
                    })
                    .catch(err => console.error("Error loading preset:", err));
            }
        });
    }

    // 3. Dynamic Sample Code Loader for Code Analysis Page
    const loadSampleBtn = document.getElementById("loadSampleBtn");
    const languageSelect = document.getElementById("language");
    const codeArea = document.getElementById("source_code");
    const fileNameInput = document.getElementById("file_name");

    if (loadSampleBtn && languageSelect && codeArea) {
        loadSampleBtn.addEventListener("click", function (e) {
            e.preventDefault();
            const lang = languageSelect.value;
            fetch(`/code-analysis/api/sample/${lang}`)
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        codeArea.value = data.code;
                        if (fileNameInput && data.filename) {
                            fileNameInput.value = data.filename;
                        }
                    }
                })
                .catch(err => console.error("Error loading sample code:", err));
        });
    }

    // 4. Threshold Slider display sync
    const thresholdSlider = document.getElementById("thresholdSlider");
    const thresholdValDisplay = document.getElementById("thresholdValDisplay");
    const thresholdInput = document.getElementById("threshold");

    if (thresholdSlider && thresholdValDisplay) {
        thresholdSlider.addEventListener("input", function () {
            const val = parseFloat(this.value).toFixed(2);
            thresholdValDisplay.textContent = val;
            if (thresholdInput) {
                thresholdInput.value = val;
            }
        });
    }
});
