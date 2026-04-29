# file_parser.py — File Text Extraction Service
# ================================================
# Extracts text content from uploaded files (PDF, TXT, DOCX).
# Think of it as a Strategy Pattern — each file type has its own parser.
#
# .NET comparison:
#   public interface IFileParser { string ExtractText(Stream file); }
#   public class PdfParser : IFileParser { ... }
#   public class DocxParser : IFileParser { ... }

import io

import docx
import fitz  # PyMuPDF

# Allowed file extensions and their MIME types (security: double validation)
ALLOWED_TYPES: dict[str, list[str]] = {
    ".pdf": ["application/pdf"],
    ".txt": ["text/plain"],
    ".docx": [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ],
    ".jpg": ["image/jpeg"],
    ".jpeg": ["image/jpeg"],
    ".png": ["image/png"],
}

# Image extensions handled separately by image_analyzer.py
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def get_file_extension(filename: str) -> str:
    """Extract lowercase file extension from filename."""
    dot_index = filename.rfind(".")
    if dot_index == -1:
        return ""
    return filename[dot_index:].lower()


def is_image_file(filename: str) -> bool:
    """Check if the file is an image type (handled by Vision API)."""
    return get_file_extension(filename) in IMAGE_EXTENSIONS


def validate_file(filename: str, content_type: str | None, size: int) -> str | None:
    """
    Validate file type and size. Returns error message or None if valid.

    Security: validates BOTH extension and MIME type to prevent
    malicious file uploads disguised with wrong extensions.
    """
    ext = get_file_extension(filename)

    if ext not in ALLOWED_TYPES:
        allowed = ", ".join(ALLOWED_TYPES.keys())
        return f"Unsupported file type: '{ext}'. Allowed: {allowed}"

    if content_type and content_type not in ALLOWED_TYPES[ext]:
        return f"MIME type mismatch: got '{content_type}' for '{ext}' file"

    if size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE // (1024 * 1024)
        return f"File too large: {size / (1024 * 1024):.1f} MB. Max: {max_mb} MB"

    return None


def sanitize_filename(filename: str) -> str:
    """
    Remove path components to prevent path traversal attacks.
    '../../etc/passwd' -> 'passwd'
    """
    # Strip any directory components
    clean = filename.replace("\\", "/").split("/")[-1]
    # Remove any null bytes
    clean = clean.replace("\x00", "")
    return clean if clean else "unnamed_file"


async def extract_text(filename: str, content: bytes) -> str:
    """
    Extract text from a file based on its extension.
    Routes to the appropriate parser function.

    .NET comparison:
    public string ExtractText(string filename, byte[] content) =>
        Path.GetExtension(filename) switch {
            ".pdf"  => ExtractFromPdf(content),
            ".docx" => ExtractFromDocx(content),
            ".txt"  => ExtractFromTxt(content),
            _ => throw new NotSupportedException()
        };
    """
    ext = get_file_extension(filename)

    if ext == ".pdf":
        return _extract_from_pdf(content)
    elif ext == ".docx":
        return _extract_from_docx(content)
    elif ext == ".txt":
        return _extract_from_txt(content)
    else:
        raise ValueError(f"Cannot extract text from '{ext}' files")


def _extract_from_pdf(content: bytes) -> str:
    """
    Extract text from PDF using PyMuPDF (fitz).
    Reads all pages and concatenates text.
    """
    text_parts = []
    with fitz.open(stream=content, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text())

    text = "\n".join(text_parts).strip()
    if not text:
        raise ValueError(
            "PDF contains no extractable text (might be scanned/image-based)"
        )
    return text


def _extract_from_docx(content: bytes) -> str:
    """
    Extract text from DOCX using python-docx.
    Reads all paragraphs and joins them.
    """
    doc = docx.Document(io.BytesIO(content))
    text = "\n".join(para.text for para in doc.paragraphs if para.text.strip())

    if not text:
        raise ValueError("DOCX contains no text content")
    return text


def _extract_from_txt(content: bytes) -> str:
    """
    Decode text file content. Tries UTF-8 first, falls back to latin-1.
    """
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    text = text.strip()
    if not text:
        raise ValueError("TXT file is empty")
    return text
