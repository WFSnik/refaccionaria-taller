(() => {
  // Selectores encadenados marca → modelo → año del buscador por vehículo.
  const form = document.querySelector("form[data-vehiculo]");
  if (!form) return;
  const q = form.elements.q;
  const marca = form.elements.marca;
  const modelo = form.elements.modelo;
  const anio = form.elements.anio;

  const llenar = (select, valores, rotulo, elegido) => {
    select.replaceChildren(new Option(rotulo, ""), ...valores.map((v) => new Option(v, v, false, String(v) === String(elegido))));
    select.disabled = valores.length === 0;
  };

  const pedir = async (params) => {
    const r = await fetch(`${form.dataset.opciones}?${new URLSearchParams(params)}`, { headers: { Accept: "application/json" } });
    return r.ok ? r.json() : {};
  };

  const cargarModelos = async (elegido) => {
    llenar(anio, [], "Año");
    if (!marca.value) { llenar(modelo, [], "Modelo"); return; }
    const datos = await pedir({ marca: marca.value });
    llenar(modelo, datos.modelos || [], "Modelo", elegido);
  };

  const cargarAnios = async (elegido) => {
    if (!modelo.value) { llenar(anio, [], "Año"); return; }
    const datos = await pedir({ marca: marca.value, modelo: modelo.value });
    llenar(anio, datos.anios || [], "Año", elegido);
  };

  // Usar los selectores reemplaza lo escrito, para no mezclar dos búsquedas.
  marca.addEventListener("change", () => { q.value = ""; cargarModelos(); });
  modelo.addEventListener("change", () => { q.value = ""; if (modelo.value) form.requestSubmit(); });
  anio.addEventListener("change", () => form.requestSubmit());
  q.addEventListener("input", () => {
    if (!marca.value) return;
    marca.value = "";
    llenar(modelo, [], "Modelo");
    llenar(anio, [], "Año");
  });

  if (marca.value) {
    cargarModelos(modelo.dataset.valor).then(() => cargarAnios(anio.dataset.valor));
  }
})();
