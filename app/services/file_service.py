from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import ALLOWED_CONTENT_TYPES, MAX_FILE_SIZE, UPLOAD_DIR
from app.models.document_model import Document
from app.models.file_model import File as FileModel
from app.schemas.files_schema import (
    FileCreate,
    FileInDB,
    FileListItem,
    FileListResponse,
)


def _validate_file_type(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. "
            "Allowed: PDF, DOCX, images (PNG/JPEG), CSV, TXT.",
        )


def _validate_file_size(size: int) -> None:
    if size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file is not allowed.",
        )

    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max size is {MAX_FILE_SIZE} bytes.",
        )


async def save_upload_file(file: UploadFile) -> dict:
    # 1. Validate content type
    _validate_file_type(file)

    # 2. Read content
    contents = await file.read()
    size = len(contents)

    # 3. Validate size
    _validate_file_size(size)

    # 4. Generate unique file id & path
    import uuid

    file_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix
    stored_name = f"{file_id}{ext}"
    stored_path = UPLOAD_DIR / stored_name

    # 5. Save to disk
    with stored_path.open("wb") as f:
        f.write(contents)

    # 6. Reset stream pointer nếu cần dùng lại
    await file.seek(0)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "stored_name": stored_name,
        "content_type": file.content_type,
        "size": size,
        "path": str(stored_path),
    }


def create_file(
    db: Session,
    data: FileCreate,
    uploaded_by_user_id: int | None = None,
) -> tuple[FileModel, Document]:
    """
    Tạo bản ghi File trong DB và đồng thời tạo luôn Document tương ứng.
    Document lúc này chưa có text_content (chưa OCR), chỉ gắn với metadata file.
    """
    # 1. Tạo bản ghi File
    db_file = FileModel(
        file_id=data.file_id,
        filename=data.filename,
        stored_name=data.stored_name,
        content_type=data.content_type,
        size=data.size,
        path=data.path,
        uploaded_by_user_id=uploaded_by_user_id,
    )
    db.add(db_file)

    # 2. Chuẩn bị owner_id (tạm thời nếu chưa có auth)
    owner_id = uploaded_by_user_id or 1  # TODO: sau này thay bằng current_user.id

    # 3. Tạo Document đúng theo document_model.py
    doc = Document(
        name=data.filename,
        original_filename=data.filename,
        file_path=data.path,
        file_size=data.size,
        content_type=data.content_type,
        owner_id=owner_id,
        # status sẽ dùng default = "pending"
        # text_content = None (chưa OCR)
    )
    db.add(doc)

    # 4. Commit một lần cho cả File + Document
    db.commit()
    db.refresh(db_file)
    db.refresh(doc)

    return db_file, doc


def get_file_by_file_id(db: Session, file_id: str) -> FileInDB | None:
    db_file = (
        db.query(FileModel)
        .filter(FileModel.file_id == file_id, FileModel.is_deleted.is_(False))
        .first()
    )
    if not db_file:
        return None
    return FileInDB.model_validate(db_file)


def list_files(db: Session, skip: int = 0, limit: int = 20) -> FileListResponse:
    query = db.query(FileModel).filter(FileModel.is_deleted.is_(False))

    total = query.count()
    db_files = (
        query.order_by(FileModel.created_at.desc()).offset(skip).limit(limit).all()
    )

    items = [FileListItem.model_validate(f) for f in db_files]
    return FileListResponse(items=items, total=total)


def soft_delete_file(db: Session, file_id: str) -> bool:
    db_file = (
        db.query(FileModel)
        .filter(FileModel.file_id == file_id, FileModel.is_deleted.is_(False))
        .first()
    )
    if not db_file:
        return False

    db_file.is_deleted = True
    db.commit()
    return True
