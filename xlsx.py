"""Minimal .xlsx reader, plus a tiny writer for demo data and tests. Standard library only.

Reading the whole file locally is much faster than the Graph workbook API (one download instead of
one slow call per tab), and the file is small.
"""
import io
import posixpath
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _col_index(ref):
    """'AB12' -> 27 (0-based column)."""
    n = 0
    for ch in ref:
        if not ch.isalpha():
            break
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def _rels(z, part):
    """Relationship id -> absolute part path for `part` (e.g. 'xl/workbook.xml')."""
    folder, name = posixpath.split(part)
    rels_path = posixpath.join(folder, "_rels", name + ".rels")
    out = {}
    if rels_path not in z.namelist():
        return out
    for el in ET.fromstring(z.read(rels_path)):
        if _local(el.tag) != "Relationship":
            continue
        target = el.get("Target", "")
        path = target.lstrip("/") if target.startswith("/") else posixpath.join(folder, target)
        out[el.get("Id")] = (posixpath.normpath(path), el.get("Type", ""))
    return out


def _shared_strings(z, path):
    out = []
    for si in ET.fromstring(z.read(path)):
        if _local(si.tag) != "si":
            continue
        parts = []
        for ch in si:  # direct <t>, or rich-text runs <r><t>; skip phonetic <rPh>
            name = _local(ch.tag)
            if name == "t":
                parts.append(ch.text or "")
            elif name == "r":
                parts.extend(t.text or "" for t in ch if _local(t.tag) == "t")
        out.append("".join(parts))
    return out


def _cell_value(c, shared):
    kind = c.get("t", "n")
    v = inline = None
    for ch in c:
        name = _local(ch.tag)
        if name == "v":
            v = ch.text
        elif name == "is":
            inline = "".join(x.text or "" for x in ch.iter() if _local(x.tag) == "t")
    if kind == "inlineStr":
        return inline
    if v is None:
        return None
    if kind == "s":
        return shared[int(v)]
    if kind == "b":
        return v == "1"
    if kind in ("str", "e"):
        return v
    try:
        return float(v)
    except ValueError:
        return v


def _sheet_rows(xml, shared):
    rows, last = {}, -1
    for _, el in ET.iterparse(io.BytesIO(xml)):
        if _local(el.tag) != "row":
            continue
        r = int(el.get("r")) - 1 if el.get("r") else last + 1
        last = r
        cells, pos = {}, 0
        for c in el:
            if _local(c.tag) != "c":
                continue
            ref = c.get("r")
            col = _col_index(ref) if ref else pos
            pos = col + 1
            val = _cell_value(c, shared)
            if val is not None and val != "":
                cells[col] = val
        if cells:
            rows[r] = cells
        el.clear()
    if not rows:
        return []
    width = max(max(c) for c in rows.values()) + 1
    return [[rows.get(i, {}).get(j) for j in range(width)] for i in range(max(rows) + 1)]


def read_workbook(data):
    """[{name, hidden, rows: [[value, ...], ...]}] in tab order. Values are str, float, bool or None."""
    z = zipfile.ZipFile(io.BytesIO(data))
    names = set(z.namelist())
    wb_path = "xl/workbook.xml"
    for path, kind in _rels(z, "").values():
        if kind.endswith("/officeDocument"):
            wb_path = path
    wb_rels = _rels(z, wb_path)
    shared = []
    for path, kind in wb_rels.values():
        if kind.endswith("/sharedStrings") and path in names:
            shared = _shared_strings(z, path)
    out = []
    for el in ET.fromstring(z.read(wb_path)).iter():
        if _local(el.tag) != "sheet":
            continue
        rid = next((v for k, v in el.attrib.items() if k.startswith("{") and _local(k) == "id"), None)
        path = wb_rels.get(rid, (None, ""))[0]
        if not path or path not in names:
            continue
        out.append({
            "name": el.get("name"),
            "hidden": el.get("state") in ("hidden", "veryHidden"),
            "rows": _sheet_rows(z.read(path), shared),
        })
    return out


# ---------------------------------------------------------------- writer (demo data, tests)

def _col_letter(i):
    s = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        s = chr(65 + rem) + s
    return s


def write_workbook(sheets):
    """sheets: [(name, rows)] where rows are lists of str / int / float / None. Returns .xlsx bytes."""
    strings, index = [], {}

    def sid(s):
        if s not in index:
            index[s] = len(strings)
            strings.append(s)
        return index[s]

    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rns = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    sheet_xml = []
    for _, rows in sheets:
        out = []
        for r, row in enumerate(rows, 1):
            cells = []
            for c, v in enumerate(row):
                if v is None or v == "":
                    continue
                ref = f"{_col_letter(c)}{r}"
                if isinstance(v, str):
                    cells.append(f'<c r="{ref}" t="s"><v>{sid(v)}</v></c>')
                else:
                    cells.append(f'<c r="{ref}"><v>{v!r}</v></c>')
            out.append(f'<row r="{r}">{"".join(cells)}</row>')
        sheet_xml.append(f'<?xml version="1.0" encoding="UTF-8"?><worksheet {ns}><sheetData>{"".join(out)}</sheetData></worksheet>')

    ct = "application/vnd.openxmlformats-officedocument.spreadsheetml"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        overrides = "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="{ct}.worksheet+xml"/>'
            for i in range(1, len(sheets) + 1))
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   f'<Override PartName="/xl/workbook.xml" ContentType="{ct}.sheet.main+xml"/>'
                   f'<Override PartName="/xl/sharedStrings.xml" ContentType="{ct}.sharedStrings+xml"/>'
                   f'{overrides}</Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'<Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/>'
                   '</Relationships>')
        tabs = "".join(f'<sheet name="{escape(name, {chr(34): "&quot;"})}" sheetId="{i}" r:id="rId{i}"/>'
                       for i, (name, _) in enumerate(sheets, 1))
        z.writestr("xl/workbook.xml",
                   f'<?xml version="1.0" encoding="UTF-8"?><workbook {ns} {rns}><sheets>{tabs}</sheets></workbook>')
        links = "".join(f'<Relationship Id="rId{i}" Type="{rel}/worksheet" Target="worksheets/sheet{i}.xml"/>'
                        for i in range(1, len(sheets) + 1))
        n = len(sheets) + 1
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'{links}<Relationship Id="rId{n}" Type="{rel}/sharedStrings" Target="sharedStrings.xml"/>'
                   '</Relationships>')
        for i, xml in enumerate(sheet_xml, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", xml)
        sst = "".join(f'<si><t xml:space="preserve">{escape(s)}</t></si>' for s in strings)
        z.writestr("xl/sharedStrings.xml",
                   f'<?xml version="1.0" encoding="UTF-8"?><sst {ns} count="{len(strings)}" '
                   f'uniqueCount="{len(strings)}">{sst}</sst>')
    return buf.getvalue()
