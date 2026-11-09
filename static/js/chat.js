(() => {
  const chat = document.querySelector("[data-chat]");
  if (!chat) return;
  const lista = chat.querySelector(".chat__mensajes");
  const form = chat.querySelector(".chat__entrada");
  const entrada = form.elements.texto;
  const boton = form.querySelector("button");
  const csrf = form.elements.csrfmiddlewaretoken.value;

  const agregar = (rol, texto) => {
    const li = document.createElement("li");
    li.className = `burbuja burbuja--${rol}`;
    li.textContent = texto;
    lista.appendChild(li);
    li.scrollIntoView({ behavior: "smooth", block: "end" });
    return li;
  };

  const enviar = async (texto) => {
    agregar("cliente", texto);
    entrada.value = "";
    boton.disabled = entrada.disabled = true;
    const espera = agregar("asistente", "");
    espera.classList.add("burbuja--escribiendo");
    espera.setAttribute("aria-label", "Escribiendo");
    try {
      const r = await fetch(chat.dataset.url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ texto }),
      });
      const datos = await r.json();
      espera.textContent = datos.respuesta || datos.error || "No pude contestar. Intenta de nuevo.";
    } catch {
      espera.textContent = "Se perdió la conexión. Intenta de nuevo.";
    } finally {
      espera.classList.remove("burbuja--escribiendo");
      espera.removeAttribute("aria-label");
      boton.disabled = entrada.disabled = false;
      entrada.focus();
    }
  };

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const texto = entrada.value.trim();
    if (texto) enviar(texto);
  });
  document.querySelectorAll("[data-sugerencia]").forEach((b) => b.addEventListener("click", () => enviar(b.textContent)));
  lista.lastElementChild?.scrollIntoView({ block: "end" });
})();
