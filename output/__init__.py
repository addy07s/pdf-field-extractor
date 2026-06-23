"""Result writers — extraction logic stays independent of output format."""

from output.csv_writer import write_csv
from output.excel_writer import write_excel

__all__ = ["write_csv", "write_excel"]
