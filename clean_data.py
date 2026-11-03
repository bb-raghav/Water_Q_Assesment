"""Remove entirely empty columns from the Bangalore CSV datasets."""

import csv
from pathlib import Path


INPUT_DIR = Path(__file__).resolve().parent / "clean_data_blr"
OUTPUT_DIR = Path(__file__).resolve().parent / "cleaned_data_blr"
NULL_MARKERS = {"", "null", "none", "nan", "na", "n/a"}
NULL_COLUMN_THRESHOLD = 0.5
def clean_csv(source: Path, destination: Path) -> tuple[int, int, int]:
    """Drop columns with no values and return (rows, original cols, kept cols)."""
    with source.open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.reader(input_file)
        header = next(reader, None)

        if header is None:
            destination.write_text("", encoding="utf-8")
            return 0, 0, 0

        rows = list(reader)

    # Drop columns with no values, all-hyphen values, or nulls in a strict
    # majority of rows. Values such as 0 are valid; retained cells stay intact.
    kept_indices = [
        index
        for index in range(len(header))
        if (
            values := [row[index].strip() for row in rows if index < len(row) and row[index].strip()]
        )
        and not all(value == "-" for value in values)
        and not (
            rows
            and sum(
                index >= len(row) or row[index].strip().casefold() in NULL_MARKERS
                for row in rows
            )
            / len(rows)
            > NULL_COLUMN_THRESHOLD
        )
    ]

    with destination.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file)
        writer.writerow([header[index] for index in kept_indices])
        for row in rows:
            writer.writerow([row[index] if index < len(row) else "" for index in kept_indices])

    return len(rows), len(header), len(kept_indices)


def main() -> None:
    if not INPUT_DIR.is_dir():
        raise FileNotFoundError(f"Input folder not found: {INPUT_DIR}")

    csv_files = sorted(INPUT_DIR.rglob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {INPUT_DIR}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total_rows = 0
    total_columns_removed = 0

    for source in csv_files:
        destination = OUTPUT_DIR / source.relative_to(INPUT_DIR)
        destination.parent.mkdir(parents=True, exist_ok=True)
        row_count, original_columns, kept_columns = clean_csv(source, destination)
        total_rows += row_count
        total_columns_removed += original_columns - kept_columns
        print(f"{source.name}: kept {kept_columns} of {original_columns} columns; preserved {row_count:,} rows")

    print(f"Done: preserved {total_rows:,} rows; removed {total_columns_removed} empty columns in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
