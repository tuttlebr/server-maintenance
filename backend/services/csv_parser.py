"""Validate the entire account import before accepting any remote work."""
import csv
import io

from pydantic import ValidationError

from backend.schemas import UserEdit, UserInfo

MAX_CSV_BYTES = 1024 * 1024
MAX_CSV_USERS = 500
COLUMNS = {"username", "full_name", "email", "groups", "shell"}
ALIASES = {"name": "full_name", "full name": "full_name", "email_address": "email", "mail": "email"}


class CsvValidationError(ValueError):
    pass


def parse_csv(content: str, mode: str = "add") -> list[UserInfo | UserEdit]:
    if mode not in {"add", "edit"}:
        raise CsvValidationError("Choose add or edit for the CSV import")
    if len(content.encode("utf-8")) > MAX_CSV_BYTES:
        raise CsvValidationError("CSV must be 1 MB or smaller")
    reader = csv.reader(io.StringIO(content.lstrip("\ufeff"), newline=""), strict=True)
    users, errors, seen = [], [], set()
    header = None
    try:
        for row in reader:
            line = reader.line_num
            if not row or not any(cell.strip() for cell in row):
                continue
            if header is None:
                candidates = [ALIASES.get(c.strip().lower(), c.strip().lower()) for c in row]
                if any(c in COLUMNS for c in candidates):
                    header = candidates
                    if len(set(header)) != len(header):
                        raise CsvValidationError("CSV has duplicate column headers")
                    unknown = set(header) - COLUMNS
                    if unknown:
                        raise CsvValidationError(f"Unknown CSV columns: {', '.join(sorted(unknown))}. Use username, full_name, email, groups, shell.")
                    if mode == "edit" and "username" not in header:
                        raise CsvValidationError("Edit CSV requires a username column")
                    if mode == "add" and ("full_name" not in header or not {"username", "email"} & set(header)):
                        raise CsvValidationError("Add CSV requires full_name and either username or email")
                    continue
                if mode == "edit":
                    raise CsvValidationError("Edit CSV requires a header row with username and the fields to change")
                header = ["full_name", "email"]  # Legacy two-column add files.
            if len(users) + len(errors) >= MAX_CSV_USERS:
                raise CsvValidationError("CSV supports at most 500 users per operation")
            if len(row) != len(header):
                errors.append(f"Row {line}: expected {len(header)} columns, got {len(row)}. Quote groups containing commas.")
                continue
            try:
                model = UserInfo if mode == "add" else UserEdit
                record = model(**{key: value.strip() for key, value in zip(header, row)})
                if record.username in seen:
                    errors.append(f"Row {line}: duplicate username '{record.username}'")
                else:
                    seen.add(record.username)
                    users.append(record)
            except ValidationError as exc:
                details = "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'account'}: {e['msg'].removeprefix('Value error, ')}" for e in exc.errors())
                errors.append(f"Row {line}: {details}")
    except csv.Error as exc:
        raise CsvValidationError(f"Row {reader.line_num}: malformed CSV ({exc})") from exc
    if errors:
        raise CsvValidationError("\n".join(errors[:20]) + (f"\n…and {len(errors) - 20} more errors" if len(errors) > 20 else ""))
    if not users:
        raise CsvValidationError("CSV contains no users")
    return users
