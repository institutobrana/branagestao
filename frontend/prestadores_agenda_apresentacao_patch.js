(function prestAgendaApresentacaoPatchV2Init() {
  if (window.__prestAgendaApresentacaoPatchV2Applied) return;
  window.__prestAgendaApresentacaoPatchV2Applied = true;
  window.__prestAgendaApresentacaoPatchApplied = true;

  var SELECT_IDS = [
    "prest-agenda-apres-particular",
    "prest-agenda-apres-convenio",
    "prest-agenda-apres-compromisso",
  ];

  var COLOR_BY_NAME = {
    amarelo: "#ffff00",
    azul: "#0000ff",
    "azul agua": "#00e5ef",
    "azul marinho": "#000080",
    branco: "#ffffff",
    cinza: "#808080",
    "cinza claro": "#d9d9d9",
    "cinza escuro": "#666666",
    lilas: "#c61ad9",
    marrom: "#8b4513",
    prata: "#c0c0c0",
    preto: "#000000",
    roxo: "#800080",
    verde: "#008000",
    "verde escuro": "#006400",
    "verde limao": "#00ff00",
    "verde oliva": "#808000",
    vermelho: "#ff0000",
  };

  var LABEL_FIX = {
    amarelo: "Amarelo",
    azul: "Azul",
    "azul agua": "Azul \u00e1gua",
    "azul marinho": "Azul marinho",
    branco: "Branco",
    cinza: "Cinza",
    "cinza claro": "Cinza claro",
    "cinza escuro": "Cinza escuro",
    lilas: "Lil\u00e1s",
    marrom: "Marrom",
    prata: "Prata",
    preto: "Preto",
    roxo: "Roxo",
    verde: "Verde",
    "verde escuro": "Verde escuro",
    "verde limao": "Verde lim\u00e3o",
    "verde oliva": "Verde oliva",
    vermelho: "Vermelho",
  };

  function norm(text) {
    return String(text || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-zA-Z ]/g, "")
      .toLowerCase()
      .trim();
  }

  function toHex(opt) {
    var rawValue = String((opt && opt.value) || "").trim();
    if (/^#[0-9a-f]{6}$/i.test(rawValue)) return rawValue;
    var key = norm(opt && opt.textContent);
    return COLOR_BY_NAME[key] || "#ffffff";
  }

  function fixedLabel(text) {
    var key = norm(text);
    return LABEL_FIX[key] || String(text || "").trim();
  }

  function fixBrokenAccentText(root) {
    if (!(root instanceof HTMLElement)) return;
    var map = [
      ["conv?nio", "convênio"],
      ["Conv?nio", "Convênio"],
      ["Obl?quo", "Oblíquo"],
      ["Ã§", "ç"],
      ["Ã£", "ã"],
      ["Ã¡", "á"],
      ["Ã©", "é"],
      ["Ã­", "í"],
      ["Ã³", "ó"],
      ["Ãº", "ú"],
      ["Ãª", "ê"],
      ["Ã´", "ô"],
    ];
    var tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    var node = tw.nextNode();
    while (node) {
      var txt = String(node.nodeValue || "");
      var fixed = txt;
      map.forEach(function (pair) {
        fixed = fixed.split(pair[0]).join(pair[1]);
      });
      if (fixed !== txt) node.nodeValue = fixed;
      node = tw.nextNode();
    }
  }

  function ensureStyle() {
    if (document.getElementById("prest-apres-patch-v2-style")) return;
    var style = document.createElement("style");
    style.id = "prest-apres-patch-v2-style";
    style.textContent = [
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-box{position:relative !important;overflow:visible !important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-field{display:block !important;margin:0 0 7px 0 !important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-field > label{display:block !important;white-space:nowrap !important;margin:0 0 2px 0 !important;font:12px Tahoma,sans-serif !important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-field > div{display:block !important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-field .prest-agenda-apres-swatch{display:none !important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-dropdown{position:relative;width:170px;font:12px Tahoma,sans-serif;z-index:9000}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-btn{width:170px;height:22px;border:1px solid #8fa7c0;background:#fff;display:grid;grid-template-columns:20px 1fr 14px;align-items:center;padding:0 4px;box-sizing:border-box;cursor:pointer}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-swatch{width:14px;height:10px;border:1px solid #222;display:inline-block}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-label{padding-left:4px;text-align:left;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-list{position:absolute;left:0;top:21px;width:170px;max-height:none;overflow:visible;background:#fff;border:1px solid #8fa7c0;z-index:9001;box-sizing:border-box}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-item{height:16px;display:grid;grid-template-columns:20px 1fr;align-items:center;gap:4px;padding:0 4px;line-height:1;cursor:pointer}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-item:hover{background:#d9e8fb}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-item.active{background:#0078d7;color:#fff}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-hidden{display:none !important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] select.prest-apres-native-hidden{display:none !important;visibility:hidden !important;position:absolute !important;left:-9999px !important;top:-9999px !important;pointer-events:none !important}",
    ].join("");
    document.head.appendChild(style);
  }

  function closeAll(exceptList) {
    var lists = document.querySelectorAll(
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-list"
    );
    var roots = document.querySelectorAll(
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-dropdown"
    );
    roots.forEach(function (root) {
      if (root instanceof HTMLElement) root.style.zIndex = "9000";
    });
    lists.forEach(function (list) {
      if (exceptList && list === exceptList) return;
      list.classList.add("easy-color-hidden");
    });
  }

  function syncPrimarySwatch(select) {
    if (!(select instanceof HTMLSelectElement)) return;
    var row = select.closest(".prest-agenda-apres-field");
    if (!(row instanceof HTMLElement)) return;
    var sw = row.querySelector(".prest-agenda-apres-swatch");
    if (!(sw instanceof HTMLElement)) return;
    var selected = select.options[select.selectedIndex] || null;
    sw.style.background = toHex(selected);
  }

  function buildDropdown(select) {
    if (!(select instanceof HTMLSelectElement)) return;
    var wrap = select.parentElement;
    if (!(wrap instanceof HTMLElement)) return;
    if (select.dataset.easyColorBuilt === "1") {
      syncPrimarySwatch(select);
      return;
    }

    var existing = wrap.querySelector(".easy-color-dropdown");
    if (existing instanceof HTMLElement) existing.remove();

    var root = document.createElement("div");
    root.className = "easy-color-dropdown";
    root.innerHTML =
      '<button type="button" class="easy-color-btn"><span class="easy-color-swatch"></span><span class="easy-color-label"></span><span>\u25bc</span></button><div class="easy-color-list easy-color-hidden"></div>';
    wrap.appendChild(root);

    var btn = root.querySelector(".easy-color-btn");
    var headSwatch = root.querySelector(".easy-color-swatch");
    var headLabel = root.querySelector(".easy-color-label");
    var list = root.querySelector(".easy-color-list");

    if (
      !(btn instanceof HTMLButtonElement) ||
      !(headSwatch instanceof HTMLElement) ||
      !(headLabel instanceof HTMLElement) ||
      !(list instanceof HTMLDivElement)
    ) {
      return;
    }

    function renderHead() {
      var selected = select.options[select.selectedIndex] || null;
      headSwatch.style.background = toHex(selected);
      headLabel.textContent = fixedLabel(selected ? selected.textContent : "");
    }

    function renderList() {
      list.innerHTML = "";
      Array.prototype.forEach.call(select.options, function (opt, idx) {
        var row = document.createElement("div");
        var label = fixedLabel(opt.textContent);
        var hex = toHex(opt);
        opt.textContent = label;
        row.className = "easy-color-item" + (idx === select.selectedIndex ? " active" : "");
        row.innerHTML =
          '<span class="easy-color-swatch" style="background:' +
          hex +
          '"></span><span class="easy-color-label">' +
          label +
          "</span>";
        row.addEventListener("click", function () {
          select.selectedIndex = idx;
          select.dispatchEvent(new Event("change", { bubbles: true }));
          renderHead();
          renderList();
          syncPrimarySwatch(select);
          closeAll();
        });
        list.appendChild(row);
      });
    }

    btn.addEventListener("click", function () {
      var open = list.classList.contains("easy-color-hidden");
      closeAll(open ? list : null);
      list.classList.toggle("easy-color-hidden", !open);
      root.style.zIndex = open ? "12000" : "9000";
    });

    select.classList.add("prest-apres-native-hidden");
    select.style.display = "none";
    select.style.visibility = "hidden";
    select.style.pointerEvents = "none";
    select.style.position = "absolute";
    select.style.left = "-9999px";
    select.style.top = "-9999px";
    select.dataset.easyColorBuilt = "1";
    select.addEventListener("change", function () {
      renderHead();
      renderList();
      syncPrimarySwatch(select);
    });

    renderHead();
    renderList();
    syncPrimarySwatch(select);
  }

  function enhanceApresentacaoPane() {
    var pane = document.querySelector("#prest-agenda-backdrop [data-tab='apresentacao']");
    if (!(pane instanceof HTMLElement)) return;
    fixBrokenAccentText(pane);

    // Remove completamente qualquer renderizador legado (refino antigo)
    // para evitar sobreposição/duplicação visual.
    var oldCombos = pane.querySelectorAll(".easy-color-combo");
    oldCombos.forEach(function (node) {
      if (node instanceof HTMLElement) node.remove();
    });

    var l1 = pane.querySelector("label[for='prest-agenda-apres-particular']");
    var l2 = pane.querySelector("label[for='prest-agenda-apres-convenio']");
    var l3 = pane.querySelector("label[for='prest-agenda-apres-compromisso']");
    if (l1) l1.textContent = "Pacientes particulares:";
    if (l2) l2.textContent = "Pacientes de conv\u00eanio:";
    if (l3) l3.textContent = "Compromissos:";

    var prevConvenio = pane.querySelector("#prest-agenda-preview-convenio");
    if (prevConvenio) prevConvenio.textContent = "Conv\u00eanio";

    var fonteBackdrop = document.getElementById("prest-agenda-fonte-backdrop");
    if (fonteBackdrop instanceof HTMLElement) fixBrokenAccentText(fonteBackdrop);

    SELECT_IDS.forEach(function (id) {
      var select = document.getElementById(id);
      if (select instanceof HTMLSelectElement) {
        // Garante que o select nativo esteja limpo antes da montagem.
        select.classList.remove("hidden");
        select.dataset.easyComboReady = "";
        buildDropdown(select);
      }
    });
  }

  function startObservers() {
    var backdrop = document.getElementById("prest-agenda-backdrop");
    if (!(backdrop instanceof HTMLElement)) return;
    if (backdrop.dataset.apresPatchObserver === "1") return;
    backdrop.dataset.apresPatchObserver = "1";

    var pending = false;
    var mo = new MutationObserver(function () {
      if (pending) return;
      pending = true;
      requestAnimationFrame(function () {
        pending = false;
        if (!backdrop.classList.contains("hidden")) enhanceApresentacaoPane();
      });
    });
    mo.observe(backdrop, { childList: true, subtree: true, attributes: true });
  }

  ensureStyle();

  document.addEventListener("click", function (ev) {
    var target = ev.target;
    if (!(target instanceof Element)) return;
    if (!target.closest("#prest-agenda-backdrop [data-tab='apresentacao'] .easy-color-dropdown")) {
      closeAll();
    }
  });

  setTimeout(function () {
    startObservers();
    enhanceApresentacaoPane();
  }, 0);

  var oldAbrir = window.prestAgendaAbrir;
  if (typeof oldAbrir === "function") {
    window.prestAgendaAbrir = function prestAgendaAbrirPatched() {
      var out = oldAbrir.apply(this, arguments);
      setTimeout(enhanceApresentacaoPane, 0);
      setTimeout(enhanceApresentacaoPane, 120);
      return out;
    };
  }

  var oldTab = window.prestAgendaTab;
  if (typeof oldTab === "function") {
    window.prestAgendaTab = function prestAgendaTabPatched(tab) {
      var out = oldTab.apply(this, arguments);
      if (String(tab || "") === "apresentacao") {
        setTimeout(enhanceApresentacaoPane, 0);
        setTimeout(enhanceApresentacaoPane, 100);
      }
      return out;
    };
  }
})();
