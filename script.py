"""Extract Bangalore Urban and Bangalore Rural records from the data CSVs."""

import csv
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_DIR = Path(__file__).resolve().parent / "clean_data_blr"
TARGET_DISTRICTS = {"BANGALORE URBAN", "BANGALORE RURAL","Bangalore Urban", "Bangalore Rural"}


def filter_csv(source: Path, destination: Path) -> tuple[int, int]:
    """Write rows for the target districts and return (rows read, rows kept)."""
    with source.open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.reader(input_file)
        header = next(reader, None)

        if header is None:
            # Preserve a completely empty CSV as an empty output file.
            destination.write_text("", encoding="utf-8")
            return 0, 0

        district_column = next(
            (index for index, name in enumerate(header) if name.strip().casefold() == "district"),
            None,
        )
        if district_column is None:
            raise ValueError(f"No 'District' column found in {source}")

        rows_read = 0
        rows_kept = 0
        with destination.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.writer(output_file)
            writer.writerow(header)

            for row in reader:
                rows_read += 1
                district = row[district_column].strip().upper() if district_column < len(row) else ""
                if district in TARGET_DISTRICTS:
                    writer.writerow(row)
                    rows_kept += 1

    return rows_read, rows_kept


def main() -> None:
    if not DATA_DIR.is_dir():
        raise FileNotFoundError(f"Data directory not found: {DATA_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_files = sorted(DATA_DIR.rglob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {DATA_DIR}")
        return

    total_read = 0
    total_kept = 0
    for source in csv_files:
        # Keep any subdirectory structure from data/ in the output directory.
        destination = OUTPUT_DIR / source.relative_to(DATA_DIR)
        destination.parent.mkdir(parents=True, exist_ok=True)
        rows_read, rows_kept = filter_csv(source, destination)
        total_read += rows_read
        total_kept += rows_kept
        print(f"{source.name}: kept {rows_kept:,} of {rows_read:,} rows")

    print(f"Done: kept {total_kept:,} of {total_read:,} rows in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
