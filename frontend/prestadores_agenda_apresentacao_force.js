(function prestAgendaApresentacaoForceInit() {
  if (window.__prestAgendaApresentacaoForceApplied) return;
  window.__prestAgendaApresentacaoForceApplied = true;

  const IDS = [
    "#prest-agenda-apres-particular",
    "#prest-agenda-apres-convenio",
    "#prest-agenda-apres-compromisso",
  ];

  function normalizeColorLabel(raw) {
    const key = String(raw || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-zA-Z ]/g, "")
      .toLowerCase()
      .trim();
    const map = {
      amarelo: "Amarelo",
      azul: "Azul",
      "azul agua": "Azul água",
      "azul marinho": "Azul marinho",
      branco: "Branco",
      cinza: "Cinza",
      "cinza claro": "Cinza claro",
      "cinza escuro": "Cinza escuro",
      lilas: "Lilás",
      marrom: "Marrom",
      prata: "Prata",
      preto: "Preto",
      roxo: "Roxo",
      verde: "Verde",
      "verde escuro": "Verde escuro",
      "verde limao": "Verde limão",
      "verde oliva": "Verde oliva",
      vermelho: "Vermelho",
    };
    return map[key] || String(raw || "").trim();
  }

  function colorFromLabel(label) {
    const key = String(label || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-zA-Z ]/g, "")
      .toLowerCase()
      .trim();
    const colors = {
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
    return colors[key] || "#ffffff";
  }

  function ensureStyle() {
    if (document.getElementById("prest-apres-force-style")) return;
    const style = document.createElement("style");
    style.id = "prest-apres-force-style";
    style.textContent = [
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-field{grid-template-columns:max-content 1fr!important;gap:8px!important;align-items:center!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-field>div{display:flex!important;align-items:center!important;gap:6px!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .prest-agenda-apres-swatch{width:18px!important;height:12px!important;border:1px solid #222!important;display:inline-block!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-force-combo{position:relative!important;width:154px!important;font:12px Tahoma,sans-serif!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-force-btn{width:154px!important;height:22px!important;border:1px solid #8fa7c0!important;background:#fff!important;display:grid!important;grid-template-columns:18px 1fr 14px!important;align-items:center!important;padding:0 4px!important;box-sizing:border-box!important;cursor:pointer!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-force-swatch{width:14px!important;height:10px!important;border:1px solid #222!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-force-label{text-align:left!important;padding-left:4px!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-force-list{position:absolute!important;left:0!important;top:21px!important;width:154px!important;max-height:336px!important;overflow:auto!important;background:#fff!important;border:1px solid #8fa7c0!important;z-index:2500!important;box-sizing:border-box!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-force-item{height:20px!important;display:grid!important;grid-template-columns:18px 1fr!important;align-items:center!important;gap:4px!important;padding:0 4px!important;cursor:pointer!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-force-item:hover{background:#d9e8fb!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-force-item.active{background:#0078d7!important;color:#fff!important}",
      "#prest-agenda-backdrop [data-tab='apresentacao'] .easy-force-hidden{display:none!important}",
    ].join("");
    document.head.appendChild(style);
  }

  function closeLists(except) {
    document.querySelectorAll(".easy-force-list").forEach((list) => {
      if (except && list === except) return;
      list.classList.add("easy-force-hidden");
    });
  }

  function syncOriginalSwatch(select) {
    const row = select.closest(".prest-agenda-apres-field");
    if (!(row instanceof HTMLElement)) return;
    const sw = row.querySelector(".prest-agenda-apres-swatch");
    if (!(sw instanceof HTMLElement)) return;
    const opt = select.selectedOptions && select.selectedOptions[0] ? select.selectedOptions[0] : null;
    sw.style.background = String(opt?.dataset?.easyColor || colorFromLabel(opt?.textContent));
  }

  function buildCombo(select) {
    if (!(select instanceof HTMLSelectElement)) return;
    const holder = select.parentElement;
    if (!(holder instanceof HTMLElement)) return;

    [...select.options].forEach((opt) => {
      const fixed = normalizeColorLabel(opt.textContent);
      opt.textContent = fixed;
      opt.dataset.easyColor = colorFromLabel(fixed);
    });

    let combo = holder.querySelector(".easy-force-combo");
    if (!(combo instanceof HTMLElement)) {
      combo = document.createElement("div");
      combo.className = "easy-force-combo";
      combo.innerHTML = [
        '<button type="button" class="easy-force-btn">',
        '<span class="easy-force-swatch"></span>',
        '<span class="easy-force-label"></span>',
        "<span>▼</span>",
        "</button>",
        '<div class="easy-force-list easy-force-hidden"></div>',
      ].join("");
      holder.appendChild(combo);
    }

    const btn = combo.querySelector(".easy-force-btn");
    const sw = combo.querySelector(".easy-force-swatch");
    const lb = combo.querySelector(".easy-force-label");
    const list = combo.querySelector(".easy-force-list");
    if (!(btn instanceof HTMLButtonElement) || !(sw instanceof HTMLElement) || !(lb instanceof HTMLElement) || !(list instanceof HTMLDivElement)) return;

    const renderList = () => {
      list.innerHTML = "";
      [...select.options].forEach((opt, idx) => {
        const item = document.createElement("div");
        item.className = "easy-force-item";
        if (idx === select.selectedIndex) item.classList.add("active");
        item.innerHTML = [
          `<span class="easy-force-swatch" style="background:${String(opt.dataset.easyColor || "#fff")}"></span>`,
          `<span class="easy-force-label">${String(opt.textContent || "")}</span>`,
        ].join("");
        item.addEventListener("click", () => {
          select.selectedIndex = idx;
          select.dispatchEvent(new Event("change", { bubbles: true }));
          syncOriginalSwatch(select);
          syncHead();
          renderList();
          closeLists();
        });
        list.appendChild(item);
      });
    };

    const syncHead = () => {
      const opt = select.selectedOptions && select.selectedOptions[0] ? select.selectedOptions[0] : null;
      lb.textContent = String(opt?.textContent || "");
      sw.style.background = String(opt?.dataset?.easyColor || "#fff");
    };

    btn.onclick = () => {
      const open = list.classList.contains("easy-force-hidden");
      closeLists(open ? list : null);
      list.classList.toggle("easy-force-hidden", !open);
    };

    select.classList.add("easy-force-hidden");
    select.addEventListener("change", () => {
      syncHead();
      renderList();
      syncOriginalSwatch(select);
    });

    syncOriginalSwatch(select);
    syncHead();
    renderList();
  }

  function apply() {
    ensureStyle();
    const pane = document.querySelector('#prest-agenda-backdrop [data-tab="apresentacao"]');
    if (!(pane instanceof HTMLElement)) return;

    setBySelector(pane, 'label[for="prest-agenda-apres-particular"]', "Pacientes particulares:");
    setBySelector(pane, 'label[for="prest-agenda-apres-convenio"]', "Pacientes de convênio:");
    setBySelector(pane, 'label[for="prest-agenda-apres-compromisso"]', "Compromissos:");
    setBySelector(pane, "#prest-agenda-preview-convenio", "Convênio");

    IDS.forEach((id) => {
      const el = pane.querySelector(id);
      if (el instanceof HTMLSelectElement) buildCombo(el);
    });
  }

  function setBySelector(root, selector, text) {
    const el = (root || document).querySelector(selector);
    if (el) el.textContent = text;
  }

  document.addEventListener("click", (ev) => {
    const tgt = ev.target;
    if (!(tgt instanceof Element)) return;
    if (!tgt.closest(".easy-force-combo")) closeLists();
    if (tgt.closest(".prest-agenda-tab") || tgt.closest("#prest-btn-agenda")) {
      setTimeout(apply, 0);
      setTimeout(apply, 100);
    }
  });

  setInterval(() => {
    const open = document.getElementById("prest-agenda-backdrop");
    if (open && !open.classList.contains("hidden")) apply();
  }, 800);

  setTimeout(apply, 0);
})();

