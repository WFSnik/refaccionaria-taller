(() => {
  const reducido = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Índice de escalonado para las animaciones de entrada.
  document.querySelectorAll(".revelar, tbody, .lista, .rejilla-ubic, .ubic-chips, .alertas-lista, .categorias").forEach((grupo) => {
    [...grupo.children].forEach((hijo, i) => hijo.style.setProperty("--i", Math.min(i, 20)));
  });

  // Números que cuentan hasta su valor.
  const formato = new Intl.NumberFormat("es-MX");
  const moneda = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 });
  document.querySelectorAll("[data-contar]").forEach((el) => {
    const final = parseFloat(el.dataset.contar) || 0;
    const fmt = el.dataset.formato === "moneda" ? moneda : formato;
    if (reducido || final === 0) { el.textContent = fmt.format(final); return; }
    const duracion = 1100;
    const retraso = parseInt(el.dataset.retraso || "150", 10);
    let inicio;
    const paso = (t) => {
      inicio ??= t;
      const avance = Math.min((t - inicio) / duracion, 1);
      const suave = 1 - Math.pow(1 - avance, 4);
      el.textContent = fmt.format(Math.round(final * suave));
      if (avance < 1) requestAnimationFrame(paso);
    };
    el.textContent = fmt.format(0);
    setTimeout(() => requestAnimationFrame(paso), retraso);
  });

  // Onda al presionar botones.
  document.addEventListener("pointerdown", (e) => {
    const btn = e.target.closest(".btn");
    if (!btn || reducido) return;
    const r = btn.getBoundingClientRect();
    const d = Math.max(r.width, r.height) * 2;
    const onda = document.createElement("span");
    onda.className = "onda";
    onda.style.cssText = `width:${d}px;height:${d}px;left:${e.clientX - r.left - d / 2}px;top:${e.clientY - r.top - d / 2}px`;
    btn.appendChild(onda);
    onda.addEventListener("animationend", () => onda.remove());
  });

  // Indicador del menú que se desliza hacia la opción activa o bajo el cursor.
  const nav = document.querySelector(".nav");
  if (nav) {
    const indicador = nav.querySelector(".nav__indicador");
    const activo = nav.querySelector('[aria-current="page"]');
    const mover = (a, animar = true) => {
      if (!a) { indicador.style.opacity = 0; return; }
      if (!animar) indicador.style.transition = "none";
      indicador.style.opacity = 1;
      indicador.style.height = `${a.offsetHeight}px`;
      indicador.style.transform = `translateY(${a.offsetTop}px)`;
      if (!animar) requestAnimationFrame(() => (indicador.style.transition = ""));
    };
    mover(activo, false);
    nav.querySelectorAll("a").forEach((a) => a.addEventListener("mouseenter", () => mover(a)));
    nav.addEventListener("mouseleave", () => mover(activo));
  }

  // Menú en pantallas chicas.
  const app = document.querySelector(".app");
  document.querySelectorAll("[data-menu]").forEach((b) =>
    b.addEventListener("click", () => app.classList.toggle("menu-abierto"))
  );

  // Filas que llevan al detalle.
  document.querySelectorAll("tr[data-href]").forEach((tr) => {
    tr.classList.add("enlace");
    tr.addEventListener("click", (e) => {
      if (e.target.closest("a, button")) return;
      location.href = tr.dataset.href;
    });
  });

  // Avisos flotantes con cierre automático.
  const cerrar = (t) => {
    if (t.classList.contains("sale")) return;
    t.classList.add("sale");
    t.addEventListener("animationend", () => t.remove(), { once: true });
  };
  document.querySelectorAll(".toast").forEach((t) => {
    t.querySelector(".toast__tiempo")?.addEventListener("animationend", () => cerrar(t));
    t.querySelector("button")?.addEventListener("click", () => cerrar(t));
  });

  // Filtros que se aplican al cambiar.
  document.querySelectorAll("form[data-auto] select").forEach((s) =>
    s.addEventListener("change", () => s.form.requestSubmit())
  );
})();
