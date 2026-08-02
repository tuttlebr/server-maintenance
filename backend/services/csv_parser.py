import csv
import io

from pydantic import ValidationError

from backend.schemas import UserInfo


def parse_csv(content: str) -> list[UserInfo]:
    """Parse CSV content into UserInfo objects.

    Expected columns: full_name, email
    The CSV may optionally include a header row.
    """
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        return []

    # Detect header row
    first_row = [c.strip().lower() for c in rows[0]]
    has_header = "full_name" in first_row or "name" in first_row or "email" in first_row

    if has_header:
        header = first_row
        data_rows = rows[1:]
    else:
        # Assume full_name, email order
        header = ["full_name", "email"]
        data_rows = rows

    # Find column indices
    name_idx = None
    email_idx = None
    for i, col in enumerate(header):
        if col in ("full_name", "name", "full name"):
            name_idx = i
        elif col in ("email", "email_address", "mail"):
            email_idx = i

    if name_idx is None:
        name_idx = 0
    if email_idx is None:
        email_idx = 1 if len(header) > 1 else 0

    users = []
    for row in data_rows:
        if not row or all(c.strip() == "" for c in row):
            continue
        full_name = row[name_idx].strip() if name_idx < len(row) else ""
        email = row[email_idx].strip() if email_idx < len(row) else ""
        if full_name and email:
            try:
                users.append(UserInfo(full_name=full_name, email=email))
            except ValidationError:
                continue

    return users


def users_to_user_info_format(users: list[UserInfo]) -> list[str]:
    """Convert UserInfo list to the Ansible user_info format: 'First Last <flast@domain>;'"""
    return [f"{u.full_name} <{u.email}>;" for u in users]


def derive_username(email: str) -> str:
    """Derive username from email (part before @)."""
    return email.split("@")[0] if "@" in email else email
