const copyButtons = document.querySelectorAll("[data-copy]");

copyButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    const text = button.getAttribute("data-copy");

    try {
      await navigator.clipboard.writeText(text);
      button.classList.add("copied");
      button.setAttribute("aria-label", "Copiado");
      setTimeout(() => {
        button.classList.remove("copied");
        button.setAttribute("aria-label", "Copiar comando");
      }, 1400);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "absolute";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      button.classList.add("copied");
      setTimeout(() => button.classList.remove("copied"), 1400);
    }
  });
});
