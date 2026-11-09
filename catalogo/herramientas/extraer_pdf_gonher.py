"""Extrae aplicaciones y equivalencias Fram del catálogo Gonher 2026 (PDF) a gonher26.json.

No es parte de la app: se corrió una vez para generar catalogo/datos/. Requiere `pip install pymupdf`.
Uso: python extraer_pdf_gonher.py CATALOGO26_FILTROS.pdf
"""
import collections, json, re, sys

import pymupdf

COLS = [("anio", 50, 110), ("motor", 110, 220), ("aceite", 220, 284), ("sintetico", 284, 345),
        ("aire", 345, 408), ("comb", 408, 470), ("cabina", 470, 612)]
CODIGO = re.compile(r"^[A-Z]{1,5}-?[0-9A-Z]+(-[0-9A-Z]+)?,?$")
SIN_SERVICIO = {"NS", "NR", "ND"}


def col(x):
    for n, a, b in COLS:
        if a <= x < b:
            return n
    return None


def lineas(page, recortar=True):
    ws = page.get_text("words")
    # Las páginas pares e impares tienen margen distinto: se alinea con el encabezado ACEITE.
    dx = next((w[0] - 237 for w in ws if w[4] == "ACEITE" and w[1] < 40), 0)
    rows = collections.defaultdict(list)
    for x0, y0, x1, y1, t, *_ in ws:
        if recortar and (x0 - dx < 45 or x0 - dx > 575):  # pestaña lateral con la marca
            continue
        rows[round(y0)].append((x0 - dx, t))
    return [(y, sorted(rows[y])) for y in sorted(rows)]


def aplicaciones(doc):
    marca = modelo = None
    salida = []
    for pg in range(3, 92):
        ls = [(y, ws) for y, ws in lineas(doc[pg]) if 55 < y < 770]
        anclas = []  # filas con año
        sueltas = []
        for y, ws in ls:
            texto = " ".join(t for _, t in ws)
            x0 = ws[0][0]
            if re.match(r"^(19|20)\d\d", ws[0][1]) and x0 < 70:
                anclas.append({"y": y, "ws": ws, "marca": marca, "modelo": modelo})
            elif 200 < x0 < 330 and re.fullmatch(r"[A-ZÁÉÍÓÚÑ\- ]+( \(Contin.a\))?", texto) and len(ws) <= 4:
                marca = re.sub(r"\s*\(Contin.a\)", "", texto).strip()
            elif x0 < 70 and not re.match(r"^[\d(]", ws[0][1]) and texto not in ("AÑO MOTOR",) and "MOTOR" not in texto:
                modelo = re.sub(r"\s*\(Contin.a\)", "", texto).strip()
            else:
                sueltas.append((y, ws))
        for y, ws in sueltas:  # se pegan a la fila con año más cercana
            if not anclas:
                continue
            a = min(anclas, key=lambda r: abs(r["y"] - y))
            if abs(a["y"] - y) <= 12:
                a.setdefault("extra", []).extend(ws)
        for a in anclas:
            celdas = collections.defaultdict(list)
            for x, t in a["ws"] + a.get("extra", []):
                celdas[col(x)].append((x, t))
            anio = " ".join(t for _, t in a["ws"][:3])
            m = re.match(r"(\d{4})(?:\s*-\s*(\d{4}))?", anio)
            fin, ini = int(m.group(1)), int(m.group(2) or m.group(1))
            fila = {"marca": a["marca"], "modelo": a["modelo"], "anio_ini": min(ini, fin), "anio_fin": max(ini, fin),
                    "motor": " ".join(t for _, t in sorted(celdas["motor"])), "pagina": pg + 1}
            for n in ("aceite", "sintetico", "aire", "comb", "cabina"):
                # Los códigos partidos en dos renglones (GP-16405- / 01T70) se unen.
                codigos = [c for c in re.split(r",\s*", " ".join(t for _, t in celdas[n]).replace("- ", "-")) if c]
                fila[n] = [m.group(0) for c in codigos for m in [re.search(r"G[A-Z]*-[0-9A-Z]+(-[0-9A-Z]+)?", c)] if m]
            if any(fila[n] for n in ("aceite", "sintetico", "aire", "comb", "cabina")):
                salida.append(fila)
    return salida


GONHER = re.compile(r"^G[A-Z]*-[0-9A-Z]+(-[0-9A-Z]+)?$")
TIPO = [("GAC-", "cabina"), ("GAF-", "cabina"), ("GG-", "comb"), ("GA", "aire"), ("GP", "aceite"), ("G-", "aceite")]


def equivalencias(doc):
    """Pares (marca, código de la otra marca, código Gonher) de las tablas de equivalencias."""
    pares = []
    for pg in range(91, 99):
        for y, ws in lineas(doc[pg], recortar=False):
            ts = [t for _, t in ws]
            for a, b in zip(ts, ts[1:]):
                if GONHER.match(b) and not GONHER.match(a) and re.search(r"\d", a):
                    marca = "INTERFIL" if "-" in a or a.startswith("UPG") else "FRAM"
                    tipo = next(t for p, t in TIPO if b.startswith(p))
                    pares.append({"tipo": tipo, "marca": marca, "codigo": a, "gonher": b, "pagina": pg + 1})
    return pares


if __name__ == "__main__":
    doc = pymupdf.open(sys.argv[1])
    apps = aplicaciones(doc)
    eqs = equivalencias(doc)
    json.dump({"aplicaciones": apps, "equivalencias": eqs}, open("gonher26.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(len(apps), "aplicaciones;", len(eqs), "equivalencias")
