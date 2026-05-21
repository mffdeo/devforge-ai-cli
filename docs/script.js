// ── Copy to clipboard ─────────────────────────────────────────────────────────

document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const text = button.getAttribute("data-copy"); // never changes
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

const translations = {
  "pt-BR": {
    "hero.title.line1": "Governança local-first",
    "hero.title.line2": "para SDLC com IA.",
    "hero.kicker": "Do scan à evidência antes do merge.",
    "hero.lead": "Classifique risco, controle contexto, aplique política e gere evidências auditáveis — tudo local, sem cloud login, pronto para o merge.",

    "nav.resources": "Recursos",
    "nav.how": "Como funciona",

    "workflow.title": "Cinco etapas. Um fluxo governado.",
    "workflow.init.desc": "Inicializa o projeto e a configuração local.",
    "workflow.scan.desc": "Mapeia stack, risco e áreas sensíveis.",
    "workflow.plan.desc": "Gera Plan Pack governado, Context Pack e Policy Decision.",
    "workflow.policy.desc": "Aplica políticas e exige evidências.",
    "workflow.evidence.desc": "Gera pacotes de evidências auditáveis.",

    "features.title": "O que o DevForge CLI faz",
    "features.prcp.desc": "Detecta stack, risco e integrações externas.",
    "features.context.desc": "Coleta contexto e metadados do repositório.",
    "features.policy.desc": "Aplica políticas organizacionais antes do merge.",
    "features.evidence.desc": "Gera pacotes de evidências auditáveis.",
    "features.local.desc": "Tudo rodando 100% local, sem cloud login.",
    "features.audit.desc": "Trilha de auditoria em NDJSON, clara e verificável.",

    "practice.title": "CLI na prática",

    "install.title": "Instale em segundos",
    "install.pipx.note": "Pacote ainda não publicado no PyPI — instale direto do GitHub.",
    "install.uv.note": "Rápido e leve com o uv.",
    "install.source.note": "Para quem quer hackear e contribuir.",

    "cta.title": "Jogue no GitHub. Leia o README. Contribua.",
    "cta.desc": "DevForge CLI é open source e feito com a comunidade. Abra issues, envie PRs e ajude a evoluir.",
    "cta.github": "Ver no GitHub",
    "cta.readme": "Abrir README",
    "cta.contribute": "Contribuir",
  },

  "en": {
    "hero.title.line1": "Local-first governance",
    "hero.title.line2": "for AI-assisted SDLC.",
    "hero.kicker": "From scan to evidence before merge.",
    "hero.lead": "Classify risk, control context, apply policy, and generate auditable evidence — fully local, no cloud login, ready before merge.",

    "nav.resources": "Features",
    "nav.how": "How it works",

    "workflow.title": "Five steps. One governed flow.",
    "workflow.init.desc": "Initializes local project governance.",
    "workflow.scan.desc": "Maps stack, risk, and sensitive areas.",
    "workflow.plan.desc": "Generates a governed Plan Pack, Context Pack, and Policy Decision.",
    "workflow.policy.desc": "Applies policies and requires evidence.",
    "workflow.evidence.desc": "Generates auditable evidence packages.",

    "features.title": "What DevForge CLI does",
    "features.prcp.desc": "Detects stack, risk, and external integrations.",
    "features.context.desc": "Collects repository context and metadata.",
    "features.policy.desc": "Applies organizational policies before merge.",
    "features.evidence.desc": "Generates auditable evidence packages.",
    "features.local.desc": "Runs 100% locally, with no cloud login.",
    "features.audit.desc": "Keeps a clear and verifiable NDJSON audit trail.",

    "practice.title": "CLI in practice",

    "install.title": "Install in seconds",
    "install.pipx.note": "Package not published on PyPI yet — install directly from GitHub.",
    "install.uv.note": "Fast and lightweight with uv.",
    "install.source.note": "For contributors who want to hack on the project.",

    "cta.title": "Star it on GitHub. Read the README. Contribute.",
    "cta.desc": "DevForge CLI is open source and community-driven. Open issues, send PRs, and help it evolve.",
    "cta.github": "View on GitHub",
    "cta.readme": "Open README",
    "cta.contribute": "Contribute",
  },
};

function applyLanguage(lang) {
  const dictionary = translations[lang] || translations["pt-BR"];

  document.querySelectorAll("[data-i18n]").forEach((element) => {
    const key = element.dataset.i18n;
    if (!dictionary[key]) return;

    // Never touch elements inside <code> or <pre>
    if (element.closest("code, pre")) return;

    element.textContent = dictionary[key];
  });

  document.querySelectorAll(".lang-btn").forEach((button) => {
    const active = button.dataset.lang === lang;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });

  document.documentElement.lang = lang === "en" ? "en" : "pt-BR";
  localStorage.setItem("devforge-lang", lang);
}

document.addEventListener("DOMContentLoaded", () => {
  const savedLang = localStorage.getItem("devforge-lang") || "pt-BR";

  document.querySelectorAll(".lang-btn").forEach((button) => {
    button.addEventListener("click", () => {
      applyLanguage(button.dataset.lang);
    });
  });

  applyLanguage(savedLang);
});
