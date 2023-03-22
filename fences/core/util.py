from typing import List, Optional

Table = List[Optional[List[str]]]


def pad(s: str, width: int) -> str:
    return " " * (width - len(s)) + s


def render_table(table: Table) -> List[str]:
    COL_DELIMITER = ' | '
    ROW_DELIMITER = '-'

    value_cell_lengths = [len(row) for row in table if row]
    if not value_cell_lengths:
        # Table is empty or contains delimiters only
        return ROW_DELIMITER * len(table)
    num_cols = max(value_cell_lengths)

    # Calc column widths
    col_widths = [0] * num_cols
    for row in table:
        if row:
            for idx, cell in enumerate(row):
                col_widths[idx] = max(col_widths[idx], len(cell))

    # Calc overall width
    width = sum(col_widths) + len(COL_DELIMITER) * (len(col_widths) - 1)

    # Output
    lines = []
    for row in table:
        line = []
        if row:
            for idx, cell in enumerate(row):
                line.append(pad(cell, col_widths[idx]))
            lines.append(COL_DELIMITER.join(line))
        else:
            lines.append(ROW_DELIMITER * width)

    return lines


def print_table(table: Table):
    lines = render_table(table)
    print("\n".join(lines))


class ConfusionMatrix:

    def __init__(self) -> None:
        self.valid_accepted = 0
        self.invalid_accepted = 0
        self.valid_rejected = 0
        self.invalid_rejected = 0

    def to_table(self) -> Table:
        total = self.valid_accepted + self.valid_rejected + self.invalid_accepted + self.invalid_rejected
        return [
            ['', 'Valid', 'Invalid', 'Total'],
            None,
            ['Accepted', str(self.valid_accepted), str(self.invalid_accepted), str(self.valid_accepted + self.invalid_accepted)],
            ['Rejected', str(self.valid_rejected), str(self.invalid_rejected), str(self.valid_rejected + self.invalid_rejected)],
            None,
            ['Total', str(self.valid_accepted + self.valid_rejected), str(self.invalid_accepted+self.invalid_rejected), str(total)],
        ]

    def render(self):
        render_table(self.to_table())

    def print(self):
        print_table(self.to_table())
