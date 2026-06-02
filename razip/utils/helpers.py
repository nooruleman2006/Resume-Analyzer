import re
import os
import uuid
from werkzeug.utils import secure_filename
from config import Config


def save_uploaded_file(file_obj, user_id):
    """
    Save an uploaded resume to disk.
    Returns (stored_path, original_filename).
    """
    original_name = secure_filename(file_obj.filename)
    ext           = original_name.rsplit('.', 1)[-1].lower()
    unique_name   = f"{user_id}_{uuid.uuid4().hex}.{ext}"

    upload_dir = Config.UPLOAD_FOLDER
    os.makedirs(upload_dir, exist_ok=True)

    stored_path = os.path.join(upload_dir, unique_name)
    file_obj.save(stored_path)
    return stored_path, original_name


def extract_keywords(text):
    """
    Very lightweight keyword extractor.
    Returns a list of unique lowercased words > 3 chars,
    excluding common stopwords.
    """
    stopwords = {
        'with','that','this','have','from','they','will','been','were',
        'their','there','your','about','into','than','then','also','some',
        'when','what','which','would','could','should','more','other',
        'after','over','such','like','just','very','even','most','only',
        'both','through','during','before','between','each','other'
    }
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    return list({w for w in words if w not in stopwords})


def format_file_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    else:
        return f"{size_bytes/(1024*1024):.1f} MB"