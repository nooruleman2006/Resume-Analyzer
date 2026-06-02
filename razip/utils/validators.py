import os
import mimetypes
from config import Config

# Allowed MIME types mapped to extensions
ALLOWED_MIMETYPES = {
    'application/pdf',
    'application/msword',                                                    # .doc
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
}

def allowed_file(filename):
    """Check if uploaded file has an allowed extension."""
    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
    )


def allowed_mimetype(file_obj):
    """
    Validate file by reading its first 8 bytes (magic bytes).
    Returns True if the file content matches an allowed type.
    Falls back to extension check if detection is inconclusive.
    """
    header = file_obj.read(8)
    file_obj.seek(0)  # always rewind

    # PDF: %PDF
    if header[:4] == b'%PDF':
        return True
    # DOCX / DOC (ZIP-based Office Open XML): PK\x03\x04
    if header[:4] == b'PK\x03\x04':
        return True
    # Legacy .doc (OLE2 Compound Document): D0 CF 11 E0
    if header[:4] == b'\xd0\xcf\x11\xe0':
        return True

    return False


def validate_password(password):
    """Return (True, '') or (False, error_message)."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number."
    return True, ''


def validate_register_form(data):
    """Validate registration form fields. Returns list of error strings."""
    errors = []
    if not data.get('first_name', '').strip():
        errors.append("First name is required.")
    if not data.get('last_name', '').strip():
        errors.append("Last name is required.")
    if not data.get('email', '').strip():
        errors.append("Email is required.")
    if '@' not in data.get('email', ''):
        errors.append("Enter a valid email address.")

    ok, msg = validate_password(data.get('password', ''))
    if not ok:
        errors.append(msg)

    if data.get('password') != data.get('confirm_password'):
        errors.append("Passwords do not match.")

    return errors
