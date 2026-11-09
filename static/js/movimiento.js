// Asistente de altas y bajas: sigue el flujo Tipo → Producto → Ubicación → Confirmar.
(() => {
  const form = document.getElementById("asistente");
  if (!form) return;
  const inicial = JSON.parse(document.getElementById("estado-inicial").textContent);
  const $ = (sel, raiz = form) => raiz.querySelector(sel);
  const $$ = (sel, raiz = form) => [...raiz.querySelectorAll(sel)];

  const pasos = $$(".paso");
  const marcadores = [...document.querySelectorAll(".pasos li")];
  const estado = {
    paso: 1,
    tipo: inicial.tipo || "",
    producto: inicial.seleccionado || null,
    crear: !!inicial.crear,
  };

  const textos = {
    ALTA: { producto: "Recibir producto", ubicacion: "Asignar ubicación", enviar: "Registrar alta", ayuda: "Escanea o escribe el código, código de barras o nombre." },
    BAJA: { producto: "Seleccionar producto", ubicacion: "Descontar de ubicación", enviar: "Registrar baja", ayuda: "Busca el producto que sale del inventario." },
  };

  // ---------- Navegación entre pasos ----------
  function irA(n, atras = false) {
    estado.paso = n;
    pasos.forEach((p) => {
      const activo = Number(p.dataset.paso) === n;
      p.classList.toggle("activo", activo);
      p.classList.toggle("atras", activo && atras);
    });
    marcadores.forEach((m, i) => {
      m.classList.toggle("hecho", i + 1 < n);
      m.classList.toggle("actual", i + 1 === n);
    });
    if (n === 2) setTimeout(() => (estado.crear ? $("#id_nuevo-nombre") : buscador).focus(), 60);
    if (n === 3) prepararUbicaciones();
    if (n === 4) pintarResumen();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  $$("[data-atras]").forEach((b) => b.addEventListener("click", () => irA(estado.paso - 1, true)));
  $$("[data-siguiente]").forEach((b) =>
    b.addEventListener("click", () => {
      if (validarPaso(estado.paso)) irA(estado.paso + 1);
    })
  );

  function marcarError(campo, mensaje) {
    const caja = campo.closest(".campo") || campo.parentElement;
    caja.classList.add("campo--error");
    let err = caja.querySelector(".error.js");
    if (!err) {
      err = document.createElement("p");
      err.className = "error js";
      caja.appendChild(err);
    }
    err.textContent = mensaje;
    campo.addEventListener("input", () => { caja.classList.remove("campo--error"); err.remove(); }, { once: true });
    campo.addEventListener("change", () => { caja.classList.remove("campo--error"); err.remove(); }, { once: true });
  }

  function validarPaso(n) {
    let ok = true;
    if (n === 2) {
      if (estado.crear) {
        $$(".bloque-nuevo [required]").forEach((c) => {
          if (!c.value.trim()) { marcarError(c, "Este campo es obligatorio."); ok = false; }
        });
      } else if (!estado.producto) {
        marcarError(buscador, "Selecciona un producto de la lista.");
        ok = false;
      }
    }
    if (n === 3) {
      if (!$('input[name="ubicacion"]:checked')) {
        marcarError($(".ubic-opciones"), "Elige una ubicación.");
        ok = false;
      }
      const cant = parseInt(cantidad.value, 10);
      if (!(cant > 0)) { marcarError(cantidad, "Indica una cantidad mayor a cero."); ok = false; }
      if (!motivo.value) { marcarError(motivo, "Elige el motivo."); ok = false; }
    }
    return ok;
  }

  // ---------- Paso 1: tipo ----------
  function aplicarTipo(tipo) {
    estado.tipo = tipo;
    const t = textos[tipo];
    $("#titulo-producto").textContent = t.producto;
    $("#ayuda-producto").textContent = t.ayuda;
    $("#titulo-ubicacion").textContent = t.ubicacion;
    $("#btn-enviar").lastChild.textContent = ` ${t.enviar}`;
    const previo = motivo.value;
    motivo.innerHTML = '<option value="">Elige un motivo</option>' +
      inicial.motivos[tipo].map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
    if (inicial.motivos[tipo].some(([v]) => v === previo)) motivo.value = previo;
    else if (tipo === "ALTA") motivo.value = "COMPRA";
    else motivo.value = "VENTA";
    if (tipo === "BAJA" && estado.crear) cancelarNuevo();
  }
  $$('input[name="tipo"]').forEach((r) =>
    // "click" también dispara al volver a elegir la misma opción.
    r.addEventListener("click", () => {
      aplicarTipo(r.value);
      if (estado.producto && estado.producto.stock === 0 && r.value === "BAJA") limpiarSeleccion();
      setTimeout(() => irA(2), 280);
    })
  );

  // ---------- Paso 2: producto ----------
  const buscador = $("#buscar-producto");
  const lista = $("#resultados");
  const tarjeta = $("#seleccion");
  const inputProducto = $('input[name="producto"]');
  const inputCrear = $('input[name="crear_producto"]');
  const bloqueNuevo = $(".bloque-nuevo");
  let temporizador, controlador;

  const escapar = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const estadoStock = (p) => (p.stock <= 0 ? "agotado" : p.stock <= p.punto_reorden ? "bajo" : "ok");
  const nivelHTML = (stock, reorden, tamano = "") => {
    const cap = Math.max(reorden * 3, stock, 1);
    const est = stock <= 0 ? "agotado" : stock <= reorden ? "bajo" : "ok";
    return `<span class="nivel nivel--${est} ${tamano}" style="--pct:${(stock / cap) * 100}%;--reorden:${(reorden / cap) * 100}%" role="img" aria-label="Stock ${stock}, punto de reorden ${reorden}"><span class="nivel__liquido"></span><span class="nivel__marca"></span></span>`;
  };
  const detalle = (p) => [p.marca, p.presentacion, p.especificacion].filter(Boolean).map(escapar).join(" · ");

  buscador.addEventListener("input", () => {
    clearTimeout(temporizador);
    temporizador = setTimeout(buscar, 180);
  });
  buscador.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      // Un escáner de código de barras termina con Enter: si hay coincidencia exacta, se toma.
      clearTimeout(temporizador);
      buscar(true);
    }
    if (e.key === "ArrowDown") { e.preventDefault(); lista.querySelector("button")?.focus(); }
  });
  lista.addEventListener("keydown", (e) => {
    const botones = [...lista.querySelectorAll("button")];
    const i = botones.indexOf(document.activeElement);
    if (e.key === "ArrowDown") { e.preventDefault(); botones[Math.min(i + 1, botones.length - 1)]?.focus(); }
    if (e.key === "ArrowUp") { e.preventDefault(); i <= 0 ? buscador.focus() : botones[i - 1].focus(); }
  });

  async function buscar(tomarExacto = false) {
    const q = buscador.value.trim();
    if (!q) { lista.hidden = true; lista.innerHTML = ""; return; }
    controlador?.abort();
    controlador = new AbortController();
    let datos;
    try {
      const r = await fetch(`${inicial.api}?q=${encodeURIComponent(q)}`, { signal: controlador.signal, headers: { Accept: "application/json" } });
      datos = (await r.json()).resultados;
    } catch (err) {
      if (err.name === "AbortError") return;
      lista.hidden = false;
      lista.innerHTML = '<li class="sin-resultados"><p>No se pudo consultar el catálogo. Revisa la conexión e intenta de nuevo.</p></li>';
      return;
    }
    const exacto = datos.find((p) => p.codigo.toLowerCase() === q.toLowerCase() || p.codigo_barras === q);
    if (tomarExacto && exacto) { elegir(exacto); return; }
    pintarResultados(datos, q);
  }

  function pintarResultados(datos, q) {
    lista.hidden = false;
    if (!datos.length) {
      lista.innerHTML = estado.tipo === "ALTA"
        ? `<li class="sin-resultados"><p>“${escapar(q)}” no está registrado.</p><button type="button" class="btn btn--ambar" id="btn-nuevo">Dar de alta producto nuevo</button></li>`
        : `<li class="sin-resultados"><p>No hay productos que coincidan con “${escapar(q)}”.</p></li>`;
      $("#btn-nuevo")?.addEventListener("click", () => abrirNuevo(q));
      return;
    }
    lista.innerHTML = datos.map((p, i) => `
      <li style="--i:${i}"><button type="button" data-id="${p.id}">
        <span class="crece"><strong>${escapar(p.nombre)}</strong><span><span class="codigo">${escapar(p.codigo)}</span> · ${detalle(p)}</span></span>
        ${nivelHTML(p.stock, p.punto_reorden)}
        <span class="num" style="min-width:36px;text-align:right;font-weight:650">${p.stock}</span>
      </button></li>`).join("") +
      (estado.tipo === "ALTA" ? `<li style="--i:${datos.length}"><button type="button" id="btn-nuevo" class="tenue">+ No está en la lista: dar de alta “${escapar(q)}”</button></li>` : "");
    lista.querySelectorAll("button[data-id]").forEach((b) =>
      b.addEventListener("click", () => elegir(datos.find((p) => String(p.id) === b.dataset.id)))
    );
    $("#btn-nuevo")?.addEventListener("click", () => abrirNuevo(q));
  }

  function elegir(p) {
    estado.producto = p;
    estado.crear = false;
    inputProducto.value = p.id;
    inputCrear.value = "0";
    bloqueNuevo.hidden = true;
    lista.hidden = true;
    buscador.value = "";
    pintarSeleccion();
  }

  function pintarSeleccion() {
    const p = estado.producto;
    if (!p) { tarjeta.hidden = true; return; }
    tarjeta.hidden = false;
    // Reinicia la animación de aparición.
    tarjeta.style.animation = "none"; void tarjeta.offsetWidth; tarjeta.style.animation = "";
    tarjeta.innerHTML = `
      <div class="crece">
        <span class="etiqueta-auto">Datos autocompletados</span>
        <strong>${escapar(p.nombre)}</strong>
        <p class="tenue"><span class="codigo">${escapar(p.codigo)}</span> · ${escapar(p.categoria)} · ${detalle(p)}</p>
      </div>
      <div style="text-align:right">${nivelHTML(p.stock, p.punto_reorden)}<p class="muy-tenue">Stock ${p.stock} · reorden en ${p.punto_reorden}</p></div>
      <button type="button" class="btn-icono" aria-label="Cambiar producto" id="quitar"><svg class="i"><use href="#i-x"/></svg></button>`;
    $("#quitar").addEventListener("click", () => { limpiarSeleccion(); buscador.focus(); });
  }

  function limpiarSeleccion() {
    estado.producto = null;
    inputProducto.value = "";
    tarjeta.hidden = true;
  }

  function abrirNuevo(q) {
    limpiarSeleccion();
    estado.crear = true;
    inputCrear.value = "1";
    lista.hidden = true;
    bloqueNuevo.hidden = false;
    const codigo = $("#id_nuevo-codigo");
    if (q && !codigo.value) {
      // Si parece código de barras (solo dígitos, 8+), va a ese campo.
      if (/^\d{8,}$/.test(q)) $("#id_nuevo-codigo_barras").value = q;
      else if (/^[\w-]+$/.test(q)) codigo.value = q.toUpperCase();
      else $("#id_nuevo-nombre").value = q;
    }
    setTimeout(() => (codigo.value ? $("#id_nuevo-nombre") : codigo).focus(), 50);
  }

  function cancelarNuevo() {
    estado.crear = false;
    inputCrear.value = "0";
    bloqueNuevo.hidden = true;
  }
  $("#cancelar-nuevo").addEventListener("click", () => { cancelarNuevo(); buscador.focus(); });

  // ---------- Paso 3: ubicación, cantidad y motivo ----------
  const cantidad = $("#id_cantidad");
  const motivo = $("#id_motivo");
  const avisoStock = $("#aviso-stock");

  function existenciaEn(id) {
    const e = estado.producto?.existencias.find((x) => String(x.ubicacion) === String(id));
    return e ? e.cantidad : 0;
  }

  function prepararUbicaciones() {
    const baja = estado.tipo === "BAJA";
    $$(".ubic-opcion").forEach((op) => {
      const radio = op.querySelector("input");
      const n = estado.crear ? 0 : existenciaEn(radio.value);
      op.querySelector("small").textContent = n ? `Tiene ${n}` : op.dataset.descripcion || "Sin existencias";
      radio.disabled = baja && n === 0;
      if (radio.disabled && radio.checked) radio.checked = false;
    });
    const disponibles = $$(".ubic-opcion input:not(:disabled)");
    if (baja && disponibles.length === 1) disponibles[0].checked = true;
    // En altas se sugiere donde ya se guarda ese producto.
    if (!baja && !$('input[name="ubicacion"]:checked') && estado.producto?.existencias.length) {
      const principal = [...estado.producto.existencias].sort((a, b) => b.cantidad - a.cantidad)[0];
      const radio = $(`.ubic-opcion input[value="${principal.ubicacion}"]`);
      if (radio) radio.checked = true;
    }
    $("#sin-ubicaciones").hidden = !(baja && disponibles.length === 0);
    revisarStock();
  }

  function revisarStock() {
    if (estado.tipo !== "BAJA" || !estado.producto) { avisoStock.hidden = true; return; }
    const sel = $('input[name="ubicacion"]:checked');
    const hay = sel ? existenciaEn(sel.value) : 0;
    const pide = parseInt(cantidad.value, 10) || 0;
    cantidad.max = sel ? hay : "";
    if (sel && pide > hay) {
      avisoStock.hidden = false;
      avisoStock.innerHTML = `<svg class="i"><use href="#i-alerta"/></svg><span>Solo hay <strong>${hay}</strong> en esta ubicación. Si continúas, la baja no se registrará${pide > estado.producto.stock ? " y se enviará una alerta de reorden a compras" : ""}.</span>`;
    } else {
      avisoStock.hidden = true;
    }
  }
  form.addEventListener("change", (e) => { if (e.target.name === "ubicacion") revisarStock(); });
  cantidad.addEventListener("input", revisarStock);
  $$("[data-paso-cantidad]").forEach((b) =>
    b.addEventListener("click", () => {
      const v = Math.max(1, (parseInt(cantidad.value, 10) || 0) + Number(b.dataset.pasoCantidad));
      cantidad.value = v;
      cantidad.animate([{ transform: "scale(1.12)" }, { transform: "scale(1)" }], { duration: 220, easing: "ease-out" });
      revisarStock();
    })
  );

  // ---------- Paso 4: resumen ----------
  function pintarResumen() {
    const ubic = $('input[name="ubicacion"]:checked');
    const n = parseInt(cantidad.value, 10) || 0;
    const p = estado.producto;
    const nombre = estado.crear ? `${$("#id_nuevo-nombre").value} (nuevo)` : p.nombre;
    const codigo = estado.crear ? $("#id_nuevo-codigo").value : p.codigo;
    const antes = estado.crear ? 0 : p.stock;
    const reorden = estado.crear ? parseInt($("#id_nuevo-punto_reorden").value, 10) || 0 : p.punto_reorden;
    const despues = estado.tipo === "ALTA" ? antes + n : Math.max(antes - n, 0);
    const filas = [
      ["Movimiento", estado.tipo === "ALTA" ? "Alta (entrada)" : "Baja (salida)"],
      ["Producto", `${escapar(nombre)}<br><span class="codigo" style="font-size:13px">${escapar(codigo)}</span>`],
      ["Ubicación", ubic ? escapar(ubic.closest(".ubic-opcion").querySelector("strong").textContent) : "—"],
      ["Cantidad", n],
      ["Motivo", escapar(motivo.selectedOptions[0]?.text || "—")],
      ["Referencia", escapar($("#id_referencia").value) || "—"],
    ];
    $("#resumen").innerHTML = filas.map(([k, v], i) => `<div style="--i:${i}"><dt>${k}</dt><dd>${v}</dd></div>`).join("") +
      `<div class="proyeccion" style="--i:${filas.length}">
        <div><dt>Stock actual</dt><dd>${antes}</dd></div>
        <svg class="i flecha"><use href="#i-flecha"/></svg>
        <div><dt>Quedará</dt><dd>${despues}</dd></div>
        <span style="margin-left:auto">${nivelHTML(despues, reorden)}</span>
      </div>`;
    const aviso = $("#aviso-reorden");
    aviso.hidden = !(despues <= reorden && (estado.tipo === "BAJA" || despues > 0));
  }

  form.addEventListener("submit", (e) => {
    if (!validarPaso(2) || !validarPaso(3)) { e.preventDefault(); return; }
    const btn = $("#btn-enviar");
    btn.disabled = true;
    btn.lastChild.textContent = " Registrando…";
  });

  // ---------- Estado inicial (incluye volver con errores del servidor) ----------
  const tipoInicial = estado.tipo;
  aplicarTipo(tipoInicial || "ALTA");
  if (inicial.motivo) motivo.value = inicial.motivo;
  if (!tipoInicial) {
    $$('input[name="tipo"]').forEach((r) => (r.checked = false));
    estado.tipo = "";
  }
  if (estado.producto) { inputProducto.value = estado.producto.id; pintarSeleccion(); }
  if (estado.crear) { bloqueNuevo.hidden = false; inputCrear.value = "1"; }
  irA(tipoInicial ? inicial.paso || 2 : 1);
})();
