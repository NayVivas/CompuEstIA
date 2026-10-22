"""Integra EXP02, EXP11 y EXP16 y crea un split sin fuga por fuentes."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import random
import re


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
EXP02_ANNOTATIONS = DATA_DIR / "dataset_exp02" / "EXP02_anotaciones.json"
EXP02_INVENTORY = DATA_DIR / "dataset_exp02" / "EXP01_paginas_inventario.csv"
EXP11_GROUND_TRUTH = DATA_DIR / "dataset_exp11" / "EXP11_GROUND_TRUTH.json"
EXP16_ANNOTATIONS = DATA_DIR / "dataset_exp16" / "EXP16_anotaciones.json"
EXP16_INVENTORY = DATA_DIR / "dataset_exp16" / "EXP16_paginas_inventario.csv"
OUTPUT_DIR = PROJECT_DIR / "Data" / "EXP17_dataset_integrado"
DATASET_JSONL = OUTPUT_DIR / "EXP17_DATASET.jsonl"
DATASET_CSV = OUTPUT_DIR / "EXP17_DATASET.csv"
GROUP_SPLIT_CSV = OUTPUT_DIR / "EXP17_SPLIT_GRUPOS.csv"
SUMMARY_JSON = OUTPUT_DIR / "EXP17_RESUMEN.json"
DOCUMENTATION_MD = OUTPUT_DIR / "EXP17_DOCUMENTACION.md"
SEED = 20260924
TARGET_RATIOS = {"train": 0.70, "validation": 0.15, "test": 0.15}
SPLITS = tuple(TARGET_RATIOS)


def _arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--semilla", type=int, default=SEED)
    parser.add_argument("--intentos", type=int, default=30_000)
    parser.add_argument("--salida", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def _read_json(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_inventory(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return {
            (row["proyecto_id"], row["documento"], int(row["pagina"])): row
            for row in csv.DictReader(stream)
        }


def _as_list(value):
    if isinstance(value, list):
        return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))
    return [] if value in (None, "") else [str(value).strip()]


def _as_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    return str(value).strip().casefold() in {"1", "true", "si", "sí", "yes"}


def _integer(value):
    try:
        return int(float(value)) if value not in (None, "") else 0
    except (TypeError, ValueError):
        return 0


def _exp02_group(project):
    match = re.fullmatch(r"Proyecto_(\d+)", project)
    number = int(match.group(1)) if match else None
    if number == 7 or (number is not None and 9 <= number <= 37):
        return "EXP02::fuente_compartida_proyectos_7_y_9_a_37"
    return f"EXP02::{project}"


def _record(row, *, origin, group, inventory, dataset_dir, relative_path):
    project = str(row.get("proyecto_id", "")).strip()
    document = str(row.get("documento", row.get("archivo", ""))).strip()
    page = int(row.get("pagina", 0))
    inventory = inventory or {}
    requires_ocr = inventory.get("requiere_ocr")
    if requires_ocr in (None, ""):
        if "tiene_texto" in inventory:
            requires_ocr = not _as_bool(inventory.get("tiene_texto"), True)
        else:
            requires_ocr = (
                _integer(row.get("palabras_pdf", 0)) == 0
                or _integer(row.get("caracteres_pdf", 0)) < 40
            )
    relative_path = Path(relative_path).as_posix()
    return {
        "registro_id": f"{origin}|||{project}|||{document}|||{page}",
        "dataset_origen": origin,
        "proyecto_id": project,
        "grupo_independencia": group,
        "documento": document,
        "pagina": page,
        "disciplinas": _as_list(row.get("disciplinas")),
        "roles_documentales": _as_list(row.get("roles_documentales")),
        "contenidos": _as_list(row.get("contenidos")),
        "decision": str(row.get("decision", "confirmada")),
        "incluir_en_metricas": _as_bool(row.get("incluir_en_metricas"), True),
        "cantidad_palabras": _integer(inventory.get("cantidad_palabras", row.get("palabras_pdf", 0))),
        "cantidad_caracteres": _integer(inventory.get("cantidad_caracteres", row.get("caracteres_pdf", 0))),
        "cantidad_imagenes": _integer(inventory.get("cantidad_imagenes", row.get("imagenes_embebidas", 0))),
        "requiere_ocr": _as_bool(requires_ocr, False),
        "ruta_relativa": relative_path,
        "archivo_disponible": (dataset_dir / relative_path).is_file(),
        "grupo_fuente": str(inventory.get("grupo_fuente", "")),
        "huella_visual_256": str(row.get("huella_visual_256", "")),
        "huella_texto": str(row.get("huella_texto", "")),
    }


def _load_records():
    records = []
    inventory02 = _read_inventory(EXP02_INVENTORY)
    for row in _read_json(EXP02_ANNOTATIONS).values():
        project, document, page = row["proyecto_id"], row["documento"], int(row["pagina"])
        records.append(_record(
            row, origin="EXP02", group=_exp02_group(project),
            inventory=inventory02.get((project, document, page)),
            dataset_dir=EXP02_ANNOTATIONS.parent,
            relative_path=(Path(project) / document).as_posix(),
        ))
    for row in _read_json(EXP11_GROUND_TRUTH).get("filas", []):
        project = row["proyecto_id"]
        document = row.get("documento", row.get("archivo", ""))
        records.append(_record(
            row, origin="EXP11", group=f"EXP11::{project}", inventory={},
            dataset_dir=EXP11_GROUND_TRUTH.parent, relative_path=document,
        ))
    inventory16 = _read_inventory(EXP16_INVENTORY)
    for row in _read_json(EXP16_ANNOTATIONS).values():
        project, document, page = row["proyecto_id"], row["documento"], int(row["pagina"])
        item = inventory16.get((project, document, page), {})
        source_group = str(item.get("grupo_fuente", "")).strip() or project
        records.append(_record(
            row, origin="EXP16", group=f"EXP16::{source_group}", inventory=item,
            dataset_dir=EXP16_ANNOTATIONS.parent,
            relative_path=item.get("ruta_relativa", ""),
        ))
    return records


def _usable(records):
    return [
        row for row in records
        if row["decision"] == "confirmada"
        and row["incluir_en_metricas"]
        and row["disciplinas"] and row["roles_documentales"] and row["contenidos"]
    ]


def _labels(row):
    return {
        f"{target}:{label}"
        for target in ("disciplinas", "roles_documentales", "contenidos")
        for label in row[target]
    }


def _group_stats(records):
    stats = {}
    for row in records:
        item = stats.setdefault(row["grupo_independencia"], {
            "paginas": 0, "labels": set(), "datasets": set(), "proyectos": set()
        })
        item["paginas"] += 1
        item["labels"].update(_labels(row))
        item["datasets"].add(row["dataset_origen"])
        item["proyectos"].add(row["proyecto_id"])
    return stats


def _ensure_train_coverage(assignment, stats):
    output = dict(assignment)
    all_labels = set().union(*(item["labels"] for item in stats.values()))
    for label in sorted(all_labels):
        if any(split == "train" and label in stats[group]["labels"] for group, split in output.items()):
            continue
        candidates = [group for group in stats if label in stats[group]["labels"]]
        selected = min(candidates, key=lambda group: (stats[group]["paginas"], group))
        output[selected] = "train"
    return output


def _score(assignment, stats, support):
    total = sum(item["paginas"] for item in stats.values())
    pages, datasets = Counter(), {split: set() for split in SPLITS}
    labels = {split: set() for split in SPLITS}
    for group, split in assignment.items():
        pages[split] += stats[group]["paginas"]
        datasets[split].update(stats[group]["datasets"])
        labels[split].update(stats[group]["labels"])
    if any(pages[split] == 0 for split in SPLITS):
        return float("inf")
    score = 100 * sum(abs(pages[s] / total - TARGET_RATIOS[s]) for s in SPLITS)
    for label, count in support.items():
        if label not in labels["train"]:
            score += 1000
        if label.startswith("disciplinas:") and count >= 10:
            score += 4 * (label not in labels["validation"])
            score += 4 * (label not in labels["test"])
    for split in SPLITS:
        score += 3 * sum(origin not in datasets[split] for origin in ("EXP02", "EXP11", "EXP16"))
    return score


def _make_split(records, seed, attempts):
    stats = _group_stats(records)
    support = Counter(label for row in records for label in _labels(row))
    fixed_group = "EXP02::fuente_compartida_proyectos_7_y_9_a_37"
    fixed = {fixed_group: "train"} if fixed_group in stats else {}
    remaining = [group for group in sorted(stats) if group not in fixed]
    rng = random.Random(seed)
    best, best_score = None, float("inf")
    for _ in range(max(1, attempts)):
        assignment = dict(fixed)
        assignment.update({
            group: rng.choices(SPLITS, weights=list(TARGET_RATIOS.values()), k=1)[0]
            for group in remaining
        })
        assignment = _ensure_train_coverage(assignment, stats)
        score = _score(assignment, stats, support)
        if score < best_score:
            best, best_score = assignment, score
    return best


def _validate(records, assignment):
    ids = [row["registro_id"] for row in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Hay identificadores repetidos.")
    group_splits = defaultdict(set)
    for row in records:
        group_splits[row["grupo_independencia"]].add(assignment[row["grupo_independencia"]])
    if any(len(value) != 1 for value in group_splits.values()):
        raise ValueError("Se detectó fuga entre splits.")
    train_labels = set().union(*(_labels(row) for row in records if assignment[row["grupo_independencia"]] == "train"))
    all_labels = set().union(*(_labels(row) for row in records))
    if all_labels - train_labels:
        raise ValueError("Hay etiquetas sin representación en TRAIN.")


def _label_matrix(records):
    counters = {split: Counter() for split in SPLITS}
    for row in records:
        counters[row["split"]].update(_labels(row))
    labels = sorted(set().union(*(set(counter) for counter in counters.values())))
    return {label: {split: counters[split][label] for split in SPLITS} for label in labels}


def _write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def build(*, seed=SEED, attempts=30_000, output=OUTPUT_DIR):
    all_records = _load_records()
    records = _usable(all_records)
    assignment = _make_split(records, seed, attempts)
    for row in records:
        row["split"] = assignment[row["grupo_independencia"]]
    records.sort(key=lambda row: (SPLITS.index(row["split"]), row["dataset_origen"], row["grupo_independencia"], row["documento"], row["pagina"]))
    _validate(records, assignment)
    output.mkdir(parents=True, exist_ok=True)
    with (output / DATASET_JSONL.name).open("w", encoding="utf-8") as stream:
        for row in records:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    fields = ["registro_id", "dataset_origen", "proyecto_id", "grupo_independencia", "split", "documento", "pagina", "disciplinas", "roles_documentales", "contenidos", "cantidad_palabras", "cantidad_caracteres", "cantidad_imagenes", "requiere_ocr", "ruta_relativa", "archivo_disponible", "grupo_fuente"]
    csv_rows = []
    for row in records:
        item = {key: row.get(key, "") for key in fields}
        for target in ("disciplinas", "roles_documentales", "contenidos"):
            item[target] = json.dumps(row[target], ensure_ascii=False)
        csv_rows.append(item)
    _write_csv(output / DATASET_CSV.name, fields, csv_rows)
    stats = _group_stats(records)
    _write_csv(output / GROUP_SPLIT_CSV.name, ["grupo_independencia", "split", "paginas", "datasets", "proyectos"], [
        {"grupo_independencia": group, "split": assignment[group], "paginas": stats[group]["paginas"], "datasets": ", ".join(sorted(stats[group]["datasets"])), "proyectos": ", ".join(sorted(stats[group]["proyectos"]))}
        for group in sorted(stats)
    ])
    split_pages = Counter(row["split"] for row in records)
    split_groups = Counter(assignment.values())
    origin_total = Counter(row["dataset_origen"] for row in all_records)
    origin_usable = Counter(row["dataset_origen"] for row in records)
    available = Counter(row["dataset_origen"] for row in records if row["archivo_disponible"])
    matrix = _label_matrix(records)
    summary = {
        "experimento": "EXP17", "semilla": seed,
        "registros_recibidos": len(all_records), "registros_utilizables": len(records),
        "registros_excluidos": len(all_records) - len(records),
        "por_origen_recibidos": dict(sorted(origin_total.items())),
        "por_origen_utilizables": dict(sorted(origin_usable.items())),
        "archivos_disponibles_por_origen": {origin: available[origin] for origin in sorted(origin_usable)},
        "archivos_faltantes_por_origen": {origin: origin_usable[origin] - available[origin] for origin in sorted(origin_usable)},
        "paginas_por_split": {split: split_pages[split] for split in SPLITS},
        "grupos_por_split": {split: split_groups[split] for split in SPLITS},
        "proporcion_paginas": {split: round(split_pages[split] / len(records), 6) for split in SPLITS},
        "etiquetas_sin_ejemplos_en_train": sorted(label for label, values in matrix.items() if values["train"] == 0),
        "cobertura_etiquetas": matrix,
    }
    (output / SUMMARY_JSON.name).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / DOCUMENTATION_MD.name).write_text(
        "# EXP17 - Dataset integrado\n\nSplit por grupos independientes, sin fuga entre proyectos o fuentes.\n\n"
        f"- TRAIN: {split_pages['train']} páginas.\n- VALIDATION: {split_pages['validation']} páginas.\n- TEST: {split_pages['test']} páginas.\n",
        encoding="utf-8",
    )
    return summary


def main():
    args = _arguments()
    print(json.dumps(build(seed=args.semilla, attempts=args.intentos, output=args.salida), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
