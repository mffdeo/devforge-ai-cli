// ── Copy to clipboard ─────────────────────────────────────────────────────────

document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const text = button.getAttribute("data-copy");
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.cssText = "position:absolute;left:-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    button.classList.add("copied");
    button.setAttribute("aria-label", "Copiado");
    setTimeout(() => {
      button.classList.remove("copied");
      button.setAttribute("aria-label", "Copiar comando");
    }, 1400);
  });
});

// ── i18n ──────────────────────────────────────────────────────────────────────

const T = {
  "pt-BR": {
    // Hero
    hero_subtitle: "Do scan à evidência antes do merge.",
    hero_lead: "Classifique risco, controle contexto, aplique política e gere evidências auditáveis — tudo local, sem cloud login, pronto para o merge.",
    // Flow
    flow_section_title: "Cinco etapas. Um fluxo governado.",
    flow_1: "Inicializa o projeto e a configuração local.",
    flow_2: "Mapeia stack, risco e áreas sensíveis.",
    flow_3: "Gera Plan Pack governado, Context Pack e Policy Decision.",
    flow_4: "Aplica políticas e exige evidências.",
    flow_5: "Gera pacotes de evidências auditáveis.",
    // Features
    features_section_title: "O que o DevForge CLI faz",
    // Install
    install_section_title: "Instale em segundos",
    install_pipx_p: "Pacote ainda não publicado no PyPI — instale direto do GitHub.",
    install_uv_p: "Rápido e leve com o uv.",
    install_git_p: "Para quem quer hackear e contribuir.",
    // CTA
    cta_h2: "Jogue no GitHub. Leia o README. Contribua.",
    cta_p: "DevForge CLI é open source e feito com a comunidade. Abra issues, envie PRs e ajude a evoluir.",
    cta_github: "Ver no GitHub",
    cta_readme: "Abrir README",
    cta_contrib: "Contribuir",
    // CLI panel
    cli_section_title: "CLI na prática",
    // H1
    h1_line1: "Governança local-first",
    h1_line2_prefix: "para ",
    h1_highlight: "SDLC com IA.",
  },
  "en": {
    // Hero
    hero_subtitle: "From scan to evidence before merge.",
    hero_lead: "Classify risk, control context, apply policy, and generate auditable evidence — fully local, no cloud login, ready before merge.",
    // Flow
    flow_section_title: "Five steps. One governed flow.",
    flow_1: "Initializes the project and local configuration.",
    flow_2: "Maps stack, risk, and sensitive areas.",
    flow_3: "Generates governed Plan Pack, Context Pack, and Policy Decision.",
    flow_4: "Applies policies and requires evidence.",
    flow_5: "Generates auditable evidence packages.",
    // Features
    features_section_title: "What DevForge CLI does",
    // Install
    install_section_title: "Install in seconds",
    install_pipx_p: "Package not yet published to PyPI — install directly from GitHub.",
    install_uv_p: "Fast and lightweight with uv.",
    install_git_p: "For those who want to hack and contribute.",
    // CTA
    cta_h2: "Star on GitHub. Read the README. Contribute.",
    cta_p: "DevForge CLI is open source and community-driven. Open issues, send PRs, and help it evolve.",
    cta_github: "View on GitHub",
    cta_readme: "Open README",
    cta_contrib: "Contribute",
    // CLI panel
    cli_section_title: "CLI in practice",
    // H1
    h1_line1: "Local-first governance",
    h1_line2_prefix: "for ",
    h1_highlight: "AI-assisted SDLC.",
  },
};

function _textNode(el) {
  for (const n of el.childNodes) {
    if (n.nodeType === Node.TEXT_NODE && n.textContent.trim()) return n;
  }
  return null;
}

function _updateSectionH2(selector, text) {
  const h2 = document.querySelector(selector);
  if (!h2) return;
  const tn = _textNode(h2);
  if (tn) tn.textContent = text;
}

function applyLanguage(lang) {
  const dict = T[lang] || T["pt-BR"];

  // data-i18n elements
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (dict[key] !== undefined) el.textContent = dict[key];
  });

  // H1 — special: has text nodes + <br> + <span>
  const h1 = document.querySelector(".hero-copy h1");
  if (h1) {
    const spans = h1.querySelectorAll("span");
    const highlight = spans[spans.length - 1];
    // text nodes: first before <br>, second after <br>
    const textNodes = [...h1.childNodes].filter(
      (n) => n.nodeType === Node.TEXT_NODE
    );
    if (textNodes[0]) textNodes[0].textContent = dict.h1_line1;
    if (textNodes[1]) textNodes[1].textContent = dict.h1_line2_prefix;
    if (highlight) highlight.textContent = dict.h1_highlight;
  }

  // Section h2 headers with decorative spans
  _updateSectionH2("#como-funciona h2", dict.flow_section_title);
  _updateSectionH2("#recursos h2", dict.features_section_title);
  _updateSectionH2(".cli-panel h2", dict.cli_section_title);
  _updateSectionH2("#install-title", dict.install_section_title);

  // Active button
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.lang === lang);
  });

  document.documentElement.lang = lang;
  localStorage.setItem("devforge_lang", lang);
}

document.querySelectorAll(".lang-btn").forEach((btn) => {
  btn.addEventListener("click", () => applyLanguage(btn.dataset.lang));
});

document.addEventListener("DOMContentLoaded", () => {
  const saved = localStorage.getItem("devforge_lang") || "pt-BR";
  applyLanguage(saved);
});
