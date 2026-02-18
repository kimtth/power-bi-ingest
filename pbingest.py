import argparse
import re
import sys
from pathlib import Path

DATATYPE_MAP = {
    "string": "string",
    "int64": "int",
    "int32": "int",
    "int16": "int",
    "double": "double",
    "decimal": "decimal",
    "dateTime": "datetime",
    "boolean": "boolean",
    "binary": "binary",
    "single": "float",
}

SKIP_TABLE_PREFIXES = ("LocalDateTable_", "DateTableTemplate_")


def find_semantic_model(project_path: Path) -> Path:
    for child in project_path.iterdir():
        if child.is_dir() and child.name.endswith(".SemanticModel"):
            return child
    raise FileNotFoundError(f"No .SemanticModel folder found in {project_path}")


def parse_tmdl_table(file_path: Path) -> dict | None:
    lines = file_path.read_text(encoding="utf-8").splitlines()

    table_name = None
    for line in lines:
        m = re.match(r"^table (.+)$", line)
        if m:
            table_name = m.group(1).strip()
            break
    if not table_name:
        return None

    columns: list[dict] = []
    measures: list[dict] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Column definition (indent level 1)
        col_m = re.match(r"^\tcolumn (.+)$", line)
        if col_m:
            col_name = col_m.group(1).strip()
            data_type = "string"
            is_hidden = False
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if nxt.strip() and len(nxt) - len(nxt.lstrip("\t")) < 2:
                    break
                dt_m = re.match(r"^\t\tdataType: (.+)$", nxt)
                if dt_m:
                    data_type = dt_m.group(1).strip()
                if nxt.strip() == "isHidden":
                    is_hidden = True
                j += 1
            columns.append({"name": col_name, "dataType": data_type, "isHidden": is_hidden})
            i += 1
            continue

        # Measure definition (indent level 1)
        meas_m = re.match(r"^\tmeasure (.+?) =(.*)$", line)
        if meas_m:
            meas_name = meas_m.group(1).strip()
            inline_expr = meas_m.group(2).strip()

            if inline_expr:
                expression = inline_expr
            else:
                # Multi-line: content is at indent level 3+; strip first 3 tabs
                expr_lines: list[str] = []
                j = i + 1
                while j < len(lines):
                    nxt = lines[j]
                    if nxt.strip():
                        if len(nxt) - len(nxt.lstrip("\t")) < 3:
                            break
                        expr_lines.append(nxt[3:])  # strip 3 leading tabs
                    elif expr_lines:
                        expr_lines.append("")  # preserve blank lines within expression
                    j += 1
                # Trim trailing blank lines
                while expr_lines and not expr_lines[-1].strip():
                    expr_lines.pop()
                expression = "\n".join(expr_lines)

            measures.append({"name": meas_name, "expression": expression})
            i += 1
            continue

        i += 1

    return {"name": table_name, "columns": columns, "measures": measures}


def parse_relationships(rel_file: Path) -> list[dict]:
    lines = rel_file.read_text(encoding="utf-8").splitlines()
    relationships: list[dict] = []
    current: dict = {}

    for line in lines:
        if re.match(r"^relationship ", line):
            if current.get("from_table") and current.get("to_table"):
                relationships.append(current)
            current = {}
        else:
            fm = re.match(r"^\tfromColumn: (.+)\.(.+)$", line)
            tm = re.match(r"^\ttoColumn: (.+)\.(.+)$", line)
            if fm:
                current["from_table"] = fm.group(1).strip()
                current["from_col"] = fm.group(2).strip()
            elif tm:
                current["to_table"] = tm.group(1).strip()
                current["to_col"] = tm.group(2).strip()

    if current.get("from_table") and current.get("to_table"):
        relationships.append(current)

    return relationships


def load_project(project_path: Path) -> tuple[list, list]:
    sm = find_semantic_model(project_path)
    tables_dir = sm / "definition" / "tables"
    rel_file = sm / "definition" / "relationships.tmdl"

    tables = []
    for f in sorted(tables_dir.glob("*.tmdl")):
        t = parse_tmdl_table(f)
        if t:
            tables.append(t)

    relationships = parse_relationships(rel_file) if rel_file.exists() else []
    return tables, relationships


def generate_measure_output(tables: list) -> str:
    parts: list[str] = []
    for t in tables:
        for m in t["measures"]:
            parts.append(f"### {t['name']}.{m['name']}\n\n```dax\n{m['expression']}\n```")
    if not parts:
        return "_No measures found._"
    return "\n\n".join(parts)


def generate_mermaid_diagram(tables: list, relationships: list) -> str:
    user_tables = {
        t["name"]: t
        for t in tables
        if not any(t["name"].startswith(p) for p in SKIP_TABLE_PREFIXES)
    }

    def sanitize(name: str) -> str:
        return re.sub(r"[^A-Za-z0-9_]", "_", name)

    # Build a mapping from original name -> sanitized name
    safe_names = {orig: sanitize(orig) for orig in user_tables}

    lines = ["```mermaid", "erDiagram"]

    for orig, t in user_tables.items():
        safe = safe_names[orig]
        lines.append(f"    {safe} {{")
        for col in t["columns"]:
            dtype = DATATYPE_MAP.get(col["dataType"], col["dataType"])
            col_name = sanitize(col["name"])
            lines.append(f"        {dtype} {col_name}")
        lines.append("    }")

    seen: set[tuple] = set()
    for rel in relationships:
        ft = rel.get("from_table", "")
        tt = rel.get("to_table", "")
        if ft in user_tables and tt in user_tables:
            key = (ft, tt)
            if key not in seen:
                seen.add(key)
                safe_ft = safe_names[ft]
                safe_tt = safe_names[tt]
                label = sanitize(rel.get("from_col", ""))
                lines.append(f'    {safe_ft} }}o--|| {safe_tt} : "{label}"')

    lines.append("```")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pbingest",
        description="Extract schema and measures from Power BI PBIP projects.",
    )
    parser.add_argument("project_path", help="Path to the PBIP project folder")
    parser.add_argument("--measure", action="store_true", help="Export measure expressions")
    parser.add_argument(
        "--table",
        action="store_true",
        help="Export table schema and relationships as a Mermaid diagram (default if no option given)",
    )
    parser.add_argument("--output", metavar="FILE", help="Write output to this file instead of stdout")

    args = parser.parse_args()

    project_path = Path(args.project_path)
    if not project_path.is_dir():
        print(f"Error: '{project_path}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    # Default to --table when no option is specified
    if not args.measure and not args.table:
        args.table = True

    try:
        tables, relationships = load_project(project_path)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    parts: list[str] = []
    if args.table:
        parts.append(generate_mermaid_diagram(tables, relationships))
    if args.measure:
        parts.append(generate_measure_output(tables))

    output = "\n\n".join(parts)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output, encoding="utf-8")
        print(f"Output written to {out_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
