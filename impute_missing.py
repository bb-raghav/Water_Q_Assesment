"""Impute missing numeric CSV values from comparable site records.

Input files are read from ``cleaned_data_blr`` and results are written to
``imputed_data_blr``. A value is estimated from records sharing the most
specific available site/location fields, such as station, district, and
coordinates. There is no dataset-wide mean fallback. Categorical columns stay
unchanged because a numeric average is not meaningful for them.
"""

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path


INPUT_DIR = Path(__file__).resolve().parent / "cleaned_data_blr"
OUTPUT_DIR = Path(__file__).resolve().parent / "imputed_data_blr"
MISSING_MARKERS = {"", "null", "none", "nan", "na", "n/a", "-"}
MIN_NUMERIC_RATIO = 0.8
LOCATION_KEY_TIERS = (
    ("station", "district", "latitude", "longitude"),
    ("station", "district"),
    ("station",),
    ("latitude", "longitude"),
    ("district", "tehsil", "block", "village"),
    ("district", "tehsil", "block"),
    ("district", "tehsil"),
    ("district",),
)


def is_missing(value: str) -> bool:
    return value.strip().casefold() in MISSING_MARKERS


def parse_number(value: str) -> Decimal | None:
    """Parse finite numeric values, allowing standard thousands separators."""
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return None
    try:
        number = Decimal(cleaned)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def format_number(value: Decimal) -> str:
    """Round an imputed value to two decimal places."""
    return f"{value:.2f}"


def similarity_distance(
    target_row: list[str],
    candidate_row: list[str],
    feature_columns: list[int],
    feature_ranges: dict[int, Decimal],
) -> Decimal | None:
    """Measure normalized numeric distance across the other observed parameters."""
    differences: list[Decimal] = []
    for column_index in feature_columns:
        if column_index >= len(target_row) or column_index >= len(candidate_row):
            continue
        target_value = parse_number(target_row[column_index])
        candidate_value = parse_number(candidate_row[column_index])
        if target_value is None or candidate_value is None:
            continue
        scale = feature_ranges.get(column_index, Decimal(0))
        if scale:
            differences.append(abs(target_value - candidate_value) / scale)
        else:
            differences.append(Decimal(0) if target_value == candidate_value else Decimal(1))
    return sum(differences, Decimal(0)) / len(differences) if differences else None


def comparable_groups(
    header: list[str], rows: list[list[str]]
) -> list[tuple[tuple[str, ...], dict[tuple[str, ...], list[int]]]]:
    """Build exact-match row groups from progressively broader location keys."""
    normalized_headers = [name.strip().casefold() for name in header]
    groups_by_tier: list[tuple[tuple[str, ...], dict[tuple[str, ...], list[int]]]] = []

    for tier in LOCATION_KEY_TIERS:
        indices = [
            next((i for i, name in enumerate(normalized_headers) if name == field), None)
            for field in tier
        ]
        if any(index is None for index in indices):
            continue

        groups: dict[tuple[str, ...], list[int]] = {}
        for row_index, row in enumerate(rows):
            values = [row[index].strip().casefold() if index < len(row) else "" for index in indices]
            # Incomplete site keys are not reliable matches.
            if any(not value or value in MISSING_MARKERS for value in values):
                continue
            groups.setdefault(tuple(values), []).append(row_index)
        groups_by_tier.append((tier, groups))

    return groups_by_tier


def impute_csv(source: Path, destination: Path) -> tuple[int, int, int]:
    """Impute by matched sites; return (rows, numeric columns, filled cells)."""
    with source.open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.reader(input_file)
        header = next(reader, None)
        rows = list(reader)

    if header is None:
        destination.write_text("", encoding="utf-8")
        return 0, 0, 0

    numeric_columns: list[int] = []
    for column_index in range(len(header)):
        observed_values: list[Decimal] = []
        non_missing_count = 0

        for row in rows:
            if column_index >= len(row) or is_missing(row[column_index]):
                continue
            non_missing_count += 1
            number = parse_number(row[column_index])
            if number is None:
                continue
            else:
                observed_values.append(number)

        # Permit occasional text contamination, but don't mistake categorical
        # columns for numeric measurements. Existing text values stay untouched.
        numeric_ratio = len(observed_values) / non_missing_count if non_missing_count else 0
        if observed_values and numeric_ratio >= MIN_NUMERIC_RATIO:
            numeric_columns.append(column_index)

    groups_by_tier = comparable_groups(header, rows)
    normalized_headers = [name.strip().casefold() for name in header]
    id_columns = {
        "slno", "state lgd code", "district lgd code", "latitude", "longitude"
    }
    feature_columns = [
        index for index in numeric_columns
        if normalized_headers[index] not in id_columns
    ]
    feature_ranges: dict[int, Decimal] = {}
    for column_index in feature_columns:
        values = [
            number
            for row in rows
            if column_index < len(row)
            and (number := parse_number(row[column_index])) is not None
        ]
        if values:
            feature_ranges[column_index] = max(values) - min(values)

    filled_cells = 0
    with destination.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(header)
        for row in rows:
            output_row = list(row)
            # Treat short/malformed rows as missing trailing cells; preserve all rows.
            if len(output_row) < len(header):
                output_row.extend([""] * (len(header) - len(output_row)))

            for column_index in numeric_columns:
                if not is_missing(output_row[column_index]):
                    continue

                # Use the first (most specific) matching site tier that has a
                # measured value for this parameter. Leave it missing if none do.
                for fields, groups in groups_by_tier:
                    indices = [normalized_headers.index(field) for field in fields]
                    key_values = [output_row[index].strip().casefold() for index in indices]
                    if any(not value or value in MISSING_MARKERS for value in key_values):
                        continue
                    key = tuple(key_values)
                    peer_indices = [
                        peer_index
                        for peer_index in groups.get(key, [])
                        if column_index < len(rows[peer_index])
                        and not is_missing(rows[peer_index][column_index])
                        and parse_number(rows[peer_index][column_index]) is not None
                    ]
                    if not peer_indices:
                        continue

                    distances = [
                        (distance, peer_index)
                        for peer_index in peer_indices
                        if (distance := similarity_distance(
                            output_row, rows[peer_index],
                            [index for index in feature_columns if index != column_index],
                            feature_ranges,
                        )) is not None
                    ]
                    if distances:
                        distances.sort(key=lambda item: item[0])
                        peer_indices = [peer_index for _, peer_index in distances[:5]]

                    peer_values = [parse_number(rows[index][column_index]) for index in peer_indices]
                    peer_values = [value for value in peer_values if value is not None]
                    if peer_values:
                        mean = sum(peer_values, Decimal(0)) / len(peer_values)
                        output_row[column_index] = format_number(mean)
                        filled_cells += 1
                        break
            writer.writerow(output_row)

    return len(rows), len(numeric_columns), filled_cells


def main() -> None:
    if not INPUT_DIR.is_dir():
        raise FileNotFoundError(f"Input folder not found: {INPUT_DIR}")

    csv_files = sorted(INPUT_DIR.rglob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {INPUT_DIR}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total_rows = 0
    total_columns = 0
    total_filled = 0

    for source in csv_files:
        destination = OUTPUT_DIR / source.relative_to(INPUT_DIR)
        destination.parent.mkdir(parents=True, exist_ok=True)
        row_count, numeric_column_count, filled_cells = impute_csv(source, destination)
        total_rows += row_count
        total_columns += numeric_column_count
        total_filled += filled_cells
        print(
            f"{source.name}: {row_count:,} rows, {numeric_column_count} numeric columns, "
            f"filled {filled_cells:,} values from matching site records"
        )

    print(
        f"Done: processed {total_rows:,} rows across {total_columns} numeric columns; "
        f"filled {total_filled:,} values in {OUTPUT_DIR}"
    )


if __name__ == "__main__":
    main()
