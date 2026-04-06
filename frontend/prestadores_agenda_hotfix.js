(function prestAgendaHotfixInit() {
  if (window.__prestAgendaHotfixApplied) return;
  window.__prestAgendaHotfixApplied = true;

  const agendaAbrirOriginal =
    typeof window.prestAgendaAbrir === "function" ? window.prestAgendaAbrir : null;

  function abrirAgendaRobusto() {
    try {
      if (typeof window.prestEnsureUI === "function") {
        window.prestEnsureUI();
      }

      if (
        typeof prestSelecionado === "function" &&
        !prestSelecionado() &&
        Array.isArray(prestadoresCache) &&
        prestadoresCache.length
      ) {
        prestadorSelId = prestadoresCache[0] && prestadoresCache[0].id ? prestadoresCache[0].id : null;
        if (typeof prestRender === "function") prestRender();
      }

      const item = typeof prestSelecionado === "function" ? prestSelecionado() : null;
      if (!item) {
        window.alert("Selecione um prestador.");
        return;
      }

      if (typeof prestAgendaEnsureUI === "function") prestAgendaEnsureUI();
      try {
        if (typeof prestAgendaEnhanceBloqueios === "function") prestAgendaEnhanceBloqueios();
      } catch (_) {}
      try {
        if (typeof prestAgendaEnhanceApresentacao === "function") prestAgendaEnhanceApresentacao();
      } catch (_) {}
      try {
        if (typeof prestAgendaEnhanceVisualizacao === "function") prestAgendaEnhanceVisualizacao();
      } catch (_) {}

      const a = prestCfg && prestCfg.agenda ? prestCfg.agenda : null;
      if (!a || !a.backdrop) {
        window.alert("N\u00e3o foi poss\u00edvel abrir a Agenda neste momento.");
        return;
      }

      const estado =
        typeof prestAgendaNovoEstado === "function"
          ? prestAgendaNovoEstado(item)
          : {
              manha_inicio: "07:00",
              manha_fim: "13:00",
              tarde_inicio: "13:00",
              tarde_fim: "20:00",
              duracao: "5",
              semana_horarios: "12",
              dia_horarios: "12",
              bloqueios_obs: "",
              apresentacao_obs: "",
              visualizacao_obs: "",
              apresentacao_particular_cor: "#ffff00",
              apresentacao_convenio_cor: "#0000ff",
              apresentacao_compromisso_cor: "#00e5ef",
              apresentacao_fonte: {},
              visualizacao_campos: [],
            };

      a.editId = Number(item.id || 0) || null;
      if (a.title) a.title.textContent = "Configura hor\u00e1rios de agendamento (" + (item.nome || "Prestador") + ")";
      if (a.manhaInicio) a.manhaInicio.value = estado.manha_inicio;
      if (a.manhaFim) a.manhaFim.value = estado.manha_fim;
      if (a.tardeInicio) a.tardeInicio.value = estado.tarde_inicio;
      if (a.tardeFim) a.tardeFim.value = estado.tarde_fim;
      if (a.duracao) a.duracao.value = estado.duracao;
      if (a.semana) a.semana.value = estado.semana_horarios;
      if (a.dia) a.dia.value = estado.dia_horarios;
      if (a.bloqueios) a.bloqueios.value = estado.bloqueios_obs;
      if (a.apresentacao) a.apresentacao.value = estado.apresentacao_obs;
      if (a.visualizacao) a.visualizacao.value = estado.visualizacao_obs;
      a.bloqueioSelId = null;
      if (a.apresParticular) a.apresParticular.value = estado.apresentacao_particular_cor;
      if (a.apresConvenio) a.apresConvenio.value = estado.apresentacao_convenio_cor;
      if (a.apresCompromisso) a.apresCompromisso.value = estado.apresentacao_compromisso_cor;
      a.apresFonteState = Object.assign({}, estado.apresentacao_fonte || {});
      if (Array.isArray(a.visualizacaoChecks)) {
        a.visualizacaoChecks.forEach((chk) => {
          chk.checked = Array.isArray(estado.visualizacao_campos)
            ? estado.visualizacao_campos.includes(chk.value)
            : false;
        });
      }

      try {
        if (typeof prestAgendaBloqueiosRender === "function") prestAgendaBloqueiosRender();
      } catch (_) {}
      try {
        if (typeof prestAgendaApresPreviewSync === "function") prestAgendaApresPreviewSync();
      } catch (_) {}
      if (a.swatchParticular && a.apresParticular) a.swatchParticular.style.background = a.apresParticular.value;
      if (a.swatchConvenio && a.apresConvenio) a.swatchConvenio.style.background = a.apresConvenio.value;
      if (a.swatchCompromisso && a.apresCompromisso) a.swatchCompromisso.style.background = a.apresCompromisso.value;

      if (typeof prestAgendaTab === "function") prestAgendaTab("escala");
      a.backdrop.classList.remove("hidden");
      setTimeout(() => {
        try {
          if (typeof prestAgendaEnhanceVisualizacao === "function") prestAgendaEnhanceVisualizacao();
        } catch (_) {}
      }, 0);
    } catch (err) {
      console.error("Falha ao abrir Agenda de prestadores:", err);
      window.alert("Falha ao abrir a agenda do prestador.");
    }
  }

  function rebinding() {
    const btn = document.getElementById("prest-btn-agenda");
    if (!btn) return;
    btn.onclick = (ev) => {
      if (ev) ev.preventDefault();
      if (typeof window.prestAgendaAbrir === "function") {
        window.prestAgendaAbrir();
        return;
      }
      abrirAgendaRobusto();
    };
    btn.dataset.agendaBound = "1";
    if (typeof prestCfg !== "undefined" && prestCfg) prestCfg.btnAgenda = btn;
  }

  const abrirOriginal = window.prestAbrir;
  if (typeof abrirOriginal === "function") {
    window.prestAbrir = async function prestAbrirComHotfix() {
      await abrirOriginal();
      rebinding();
    };
  }

  window.prestAgendaAbrir = abrirAgendaRobusto;

  document.addEventListener(
    "click",
    (ev) => {
      const btn = ev.target && ev.target.closest ? ev.target.closest("#prest-btn-agenda") : null;
      if (!btn) return;
      ev.preventDefault();
      ev.stopPropagation();
      if (typeof ev.stopImmediatePropagation === "function") ev.stopImmediatePropagation();
      if (typeof window.prestAgendaAbrir === "function") {
        window.prestAgendaAbrir();
        return;
      }
      if (typeof agendaAbrirOriginal === "function") {
        try {
          agendaAbrirOriginal();
          return;
        } catch (_) {}
      }
      abrirAgendaRobusto();
    },
    true
  );

  setTimeout(rebinding, 0);
})();
