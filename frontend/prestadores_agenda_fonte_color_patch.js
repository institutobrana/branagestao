(function prestAgendaFonteColorPatchInit() {
  if (window.__prestAgendaFonteColorPatchApplied) return;
  window.__prestAgendaFonteColorPatchApplied = true;

  var PALETTE = [
    { value: "#000000", label: "Preto" },
    { value: "#800000", label: "Bordô" },
    { value: "#008000", label: "Verde" },
    { value: "#808000", label: "Verde-oliva" },
    { value: "#000080", label: "Azul-marinho" },
    { value: "#800080", label: "Roxo" },
    { value: "#008080", label: "Azul-petróleo" },
    { value: "#808080", label: "Cinza" },
    { value: "#c0c0c0", label: "Prateado" },
    { value: "#ff0000", label: "Vermelho" },
    { value: "#00ff00", label: "Verde-limão" },
    { value: "#ffff00", label: "Amarelo" },
    { value: "#0000ff", label: "Azul" },
    { value: "#ff00ff", label: "Fúcsia" },
    { value: "#00ffff", label: "Azul-piscina" },
    { value: "#ffffff", label: "Branco" },
  ];

  var BY_VALUE = {};
  PALETTE.forEach(function (item) {
    BY_VALUE[String(item.value || "").toLowerCase()] = item;
  });

  function norm(text) {
    return String(text || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-zA-Z0-9- ]/g, "")
      .toLowerCase()
      .trim();
  }

  function findByLabel(text) {
    var key = norm(text);
    for (var i = 0; i < PALETTE.length; i += 1) {
      if (norm(PALETTE[i].label) === key) return PALETTE[i];
    }
    return null;
  }

  function ensureStyle() {
    if (document.getElementById("prest-agenda-fonte-color-patch-style")) return;
    var style = document.createElement("style");
    style.id = "prest-agenda-fonte-color-patch-style";
    style.textContent = [
      "#prest-agenda-fonte-backdrop .modal{overflow:visible!important}",
      "#prest-agenda-fonte-backdrop .modal-body{overflow:visible!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-bottom{overflow:visible!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-box{overflow:visible!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-color .easy-font-color-dropdown{position:relative!important;width:104px!important;z-index:9200!important;font:12px Tahoma,sans-serif!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-color .easy-font-color-btn{width:104px!important;height:22px!important;border:1px solid #8fa7c0!important;background:#fff!important;display:grid!important;grid-template-columns:20px 1fr 14px!important;align-items:center!important;padding:0 4px!important;box-sizing:border-box!important;cursor:pointer!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-color .easy-font-color-swatch{width:14px!important;height:10px!important;border:1px solid #222!important;display:inline-block!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-color .easy-font-color-label{text-align:left!important;padding-left:4px!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-color .easy-font-color-list{position:absolute!important;left:0!important;top:21px!important;width:104px!important;background:#fff!important;border:1px solid #8fa7c0!important;box-sizing:border-box!important;z-index:12050!important;max-height:none!important;overflow:visible!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-color .easy-font-color-item{height:16px!important;display:grid!important;grid-template-columns:20px 1fr!important;align-items:center!important;gap:4px!important;padding:0 4px!important;box-sizing:border-box!important;cursor:pointer!important;line-height:1!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-color .easy-font-color-item:hover{background:#d9e8fb!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-color .easy-font-color-item.active{background:#0078d7!important;color:#fff!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-color .easy-font-color-hidden{display:none!important}",
      "#prest-agenda-fonte-backdrop #prest-agenda-fonte-color-swatch{display:none!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-color .easy-font-color-btn > span:not(.easy-font-color-swatch){border:0!important;width:auto!important;height:auto!important;background:transparent!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-color .easy-font-color-item > span:not(.easy-font-color-swatch){border:0!important;width:auto!important;height:auto!important;background:transparent!important}",
      "#prest-agenda-fonte-backdrop .prest-agenda-font-color .easy-font-color-btn .easy-font-color-swatch,#prest-agenda-fonte-backdrop .prest-agenda-font-color .easy-font-color-item .easy-font-color-swatch{width:14px!important;height:10px!important;border:1px solid #222!important;display:inline-block!important}",
      "#prest-agenda-fonte-backdrop #prest-agenda-fonte-color.prest-fonte-native-hidden{display:none!important;visibility:hidden!important;position:absolute!important;left:-9999px!important;top:-9999px!important;pointer-events:none!important}",
    ].join("");
    document.head.appendChild(style);
  }

  function closeAll(exceptList) {
    var lists = document.querySelectorAll(
      "#prest-agenda-fonte-backdrop .prest-agenda-font-color .easy-font-color-list"
    );
    lists.forEach(function (list) {
      if (exceptList && list === exceptList) return;
      list.classList.add("easy-font-color-hidden");
    });
  }

  function ensurePalette(select) {
    if (!(select instanceof HTMLSelectElement)) return;
    var currentValue = String(select.value || "").trim().toLowerCase();
    var currentLabel =
      select.selectedOptions && select.selectedOptions[0]
        ? String(select.selectedOptions[0].textContent || "")
        : "";

    var selected = BY_VALUE[currentValue] || findByLabel(currentLabel) || PALETTE[0];
    var html = PALETTE.map(function (item) {
      return '<option value="' + item.value + '">' + item.label + "</option>";
    }).join("");
    select.innerHTML = html;
    select.value = selected.value;
  }

  function syncHeader(select, root) {
    if (!(select instanceof HTMLSelectElement) || !(root instanceof HTMLElement)) return;
    var opt = select.selectedOptions && select.selectedOptions[0] ? select.selectedOptions[0] : null;
    var sw = root.querySelector(".easy-font-color-btn .easy-font-color-swatch");
    var lb = root.querySelector(".easy-font-color-btn .easy-font-color-label");
    var item = opt ? BY_VALUE[String(opt.value || "").toLowerCase()] : null;
    var bg = item ? item.value : "#000000";
    var text = item ? item.label : String(opt ? opt.textContent : "");
    if (sw instanceof HTMLElement) sw.style.background = bg;
    if (lb instanceof HTMLElement) lb.textContent = text;
  }

  function renderList(select, root) {
    if (!(select instanceof HTMLSelectElement) || !(root instanceof HTMLElement)) return;
    var list = root.querySelector(".easy-font-color-list");
    if (!(list instanceof HTMLDivElement)) return;
    list.innerHTML = "";
    PALETTE.forEach(function (item, idx) {
      var row = document.createElement("div");
      var isActive = String(select.value || "").toLowerCase() === String(item.value).toLowerCase();
      row.className = "easy-font-color-item" + (isActive ? " active" : "");
      row.innerHTML =
        '<span class="easy-font-color-swatch" style="background:' +
        item.value +
        '"></span><span class="easy-font-color-label">' +
        item.label +
        "</span>";
      row.addEventListener("click", function () {
        select.value = item.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        syncHeader(select, root);
        renderList(select, root);
        closeAll();
      });
      list.appendChild(row);
    });
  }

  function ensureFonteColorCombo() {
    var backdrop = document.getElementById("prest-agenda-fonte-backdrop");
    var select = document.getElementById("prest-agenda-fonte-color");
    if (!(backdrop instanceof HTMLElement) || !(select instanceof HTMLSelectElement)) return;

    ensurePalette(select);
    ensureStyle();

    var wrap = select.parentElement;
    if (!(wrap instanceof HTMLElement)) return;
    var existing = wrap.querySelector(".easy-font-color-dropdown");
    if (!(existing instanceof HTMLElement)) {
      existing = document.createElement("div");
      existing.className = "easy-font-color-dropdown";
      existing.innerHTML =
        '<button type="button" class="easy-font-color-btn"><span class="easy-font-color-swatch"></span><span class="easy-font-color-label"></span><span>▼</span></button><div class="easy-font-color-list easy-font-color-hidden"></div>';
      wrap.appendChild(existing);
      var btn = existing.querySelector(".easy-font-color-btn");
      var list = existing.querySelector(".easy-font-color-list");
      if (btn instanceof HTMLButtonElement && list instanceof HTMLDivElement) {
        btn.addEventListener("click", function () {
          var willOpen = list.classList.contains("easy-font-color-hidden");
          closeAll(willOpen ? list : null);
          list.classList.toggle("easy-font-color-hidden", !willOpen);
        });
      }
      select.addEventListener("change", function () {
        syncHeader(select, existing);
        renderList(select, existing);
      });
    }

    select.classList.add("prest-fonte-native-hidden");
    syncHeader(select, existing);
    renderList(select, existing);
  }

  function uniqueSorted(values) {
    var seen = Object.create(null);
    var out = [];
    values.forEach(function (v) {
      var s = String(v || "").trim();
      if (!s) return;
      var k = s.toLowerCase();
      if (seen[k]) return;
      seen[k] = true;
      out.push(s);
    });
    out.sort(function (a, b) {
      return a.localeCompare(b, "pt-BR");
    });
    return out;
  }

  async function getSystemFontFamilies() {
    if (Array.isArray(window.__prestAgendaSystemFontsCache) && window.__prestAgendaSystemFontsCache.length) {
      return window.__prestAgendaSystemFontsCache.slice();
    }
    var families = [];
    if (typeof window.queryLocalFonts === "function") {
      try {
        var fonts = await window.queryLocalFonts();
        families = uniqueSorted(
          (fonts || []).map(function (f) {
            return f && f.family ? String(f.family) : "";
          })
        );
      } catch (_) {
        families = [];
      }
    }
    if (!families.length && typeof window.cnfRelatorioFontesDisponiveis === "function") {
      try {
        families = uniqueSorted(window.cnfRelatorioFontesDisponiveis());
      } catch (_) {
        families = [];
      }
    }
    window.__prestAgendaSystemFontsCache = families.slice();
    return families;
  }

  async function refreshFonteFamiliesFromOS() {
    var select = document.getElementById("prest-agenda-fonte-family");
    if (!(select instanceof HTMLSelectElement)) return;
    var current = String(select.value || "").trim();
    var families = await getSystemFontFamilies();
    if (!families.length) return;

    select.innerHTML = families
      .map(function (name) {
        var safe = String(name).replace(/"/g, "&quot;");
        return '<option value="' + safe + '" style="font-family:' + safe + '">' + safe + "</option>";
      })
      .join("");

    if (current && families.some(function (f) { return String(f).toLowerCase() === current.toLowerCase(); })) {
      select.value = current;
    } else {
      var preferred = families.find(function (f) { return String(f).toLowerCase() === "ms sans serif"; });
      select.value = preferred || families[0];
    }
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function ensureFonteSizeOptions() {
    var select = document.getElementById("prest-agenda-fonte-size");
    if (!(select instanceof HTMLSelectElement)) return;
    var current = String(select.value || "").trim();
    var sizes = ["8", "10", "12", "14", "15", "17", "18", "23", "24", "30"];
    select.innerHTML = sizes
      .map(function (s) {
        return '<option value="' + s + '">' + s + "</option>";
      })
      .join("");
    if (current && sizes.indexOf(current) >= 0) {
      select.value = current;
    } else {
      select.value = "8";
    }
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  document.addEventListener("click", function (ev) {
    var target = ev.target;
    if (!(target instanceof Element)) return;
    if (!target.closest("#prest-agenda-fonte-backdrop .prest-agenda-font-color .easy-font-color-dropdown")) {
      closeAll();
    }
  });

  var oldFonteAbrir = window.prestAgendaFonteAbrir;
  if (typeof oldFonteAbrir === "function") {
    window.prestAgendaFonteAbrir = function prestAgendaFonteAbrirPatched() {
      var out = oldFonteAbrir.apply(this, arguments);
      setTimeout(function () {
        ensureFonteColorCombo();
        ensureFonteSizeOptions();
        refreshFonteFamiliesFromOS();
      }, 0);
      setTimeout(function () {
        ensureFonteColorCombo();
        ensureFonteSizeOptions();
        refreshFonteFamiliesFromOS();
      }, 120);
      return out;
    };
  }

  setTimeout(function () {
    ensureFonteColorCombo();
    ensureFonteSizeOptions();
    refreshFonteFamiliesFromOS();
  }, 0);
})();
