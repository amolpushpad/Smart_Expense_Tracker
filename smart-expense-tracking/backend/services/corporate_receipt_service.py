import uuid
from pathlib import Path

from flask import current_app

from services.corporate_workflow_service import CorporateWorkflowError

MAX_RECEIPT_BYTES = 5 * 1024 * 1024
RECEIPT_SIGNATURES = {
    "pdf": (".pdf", lambda data: data.startswith(b"%PDF-")),
    "png": (".png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    "jpg": (".jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    "jpeg": (".jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
}


def receipt_root():
    configured = current_app.config.get("CORPORATE_RECEIPT_DIR")
    root = Path(configured) if configured else Path(current_app.instance_path) / "corporate_receipts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_receipt(upload, organization_id):
    filename = Path(upload.filename or "").name
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    signature = RECEIPT_SIGNATURES.get(extension)
    if not signature:
        raise CorporateWorkflowError("Receipt must be a PDF, PNG or JPG file.", errors={"receipt": "Unsupported file type."})
    contents = upload.stream.read(MAX_RECEIPT_BYTES + 1)
    if not contents:
        raise CorporateWorkflowError("The receipt file is empty.", errors={"receipt": "Empty file."})
    if len(contents) > MAX_RECEIPT_BYTES:
        raise CorporateWorkflowError("Receipt must be 5 MB or smaller.", errors={"receipt": "File too large."})
    if not signature[1](contents):
        raise CorporateWorkflowError("The file content does not match its type.", errors={"receipt": "Invalid file content."})
    relative = Path(str(organization_id)) / f"{uuid.uuid4().hex}{signature[0]}"
    target = receipt_root() / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(contents)
    return relative.as_posix(), filename[:255], target


def receipt_file(relative_path):
    if not relative_path:
        return None
    root = receipt_root().resolve()
    candidate = (root / relative_path).resolve()
    if root not in candidate.parents or not candidate.is_file():
        return None
    return candidate
