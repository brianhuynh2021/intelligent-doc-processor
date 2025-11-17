from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.files_schema import (
    FileCreate,
    FileDeleteResponse,
    FileDownloadResponse,
    UploadedFileResponse,
)
from app.services.file_service import (
    create_file,
    get_file_by_file_id,
    save_upload_file,
    soft_delete_file,
)

router = APIRouter(
    prefix="/files",
    tags=["files"],
)


@router.post(
    "/upload",
    response_model=UploadedFileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a single file via multipart/form-data.

    - Field name: `file`
    - Valid types: PDF, DOCX, images (PNG/JPEG), CSV, TXT
    """
    # 1. Lưu file vật lý (local / MinIO) + validate type/size
    meta = await save_upload_file(file)
    # meta: file_id, filename, stored_name, content_type, size, path

    # 2. Lưu metadata vào DB
    file_create = FileCreate(
        file_id=meta["file_id"],
        filename=meta["filename"],
        stored_name=meta["stored_name"],
        content_type=meta["content_type"],
        size=meta["size"],
        path=meta["path"],
    )

    db_file = create_file(db, file_create)

    # 3. Trả response cho FE (chỉ thông tin cần thiết)
    return UploadedFileResponse(
        file_id=db_file.file_id,
        filename=db_file.filename,
        content_type=db_file.content_type,
        size=db_file.size,
        url=None,  # sau này có thể build URL download từ file_id
    )


@router.get(
    "/{file_id}",
    response_model=FileDownloadResponse,
    status_code=status.HTTP_200_OK,
)
def get_file(
    file_id: str,
    db: Session = Depends(get_db),
):
    """
    Get metadata for a single file by its business ID (file_id).
    """
    db_file = get_file_by_file_id(db, file_id)
    if not db_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Optionally build a download URL based on your API prefix
    download_url = f"/api/v1/files/{file_id}/download"

    return FileDownloadResponse(
        id=db_file.id,
        file_id=db_file.file_id,
        filename=db_file.filename,
        stored_name=db_file.stored_name,
        content_type=db_file.content_type,
        size=db_file.size,
        path=db_file.path,
        created_at=db_file.created_at,
        updated_at=db_file.updated_at,
        is_deleted=db_file.is_deleted,
        url=download_url,
    )


@router.get(
    "/{file_id}/download",
    response_class=FileResponse,
    status_code=status.HTTP_200_OK,
)
def download_file(
    file_id: str,
    db: Session = Depends(get_db),
):
    """
    Download the physical file by its file_id.
    """
    db_file = get_file_by_file_id(db, file_id)
    if not db_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    return FileResponse(
        path=db_file.path,
        media_type=db_file.content_type,
        filename=db_file.filename,
    )


@router.delete(
    "/{file_id}",
    response_model=FileDeleteResponse,
    status_code=status.HTTP_200_OK,
)
def delete_file(
    file_id: str,
    db: Session = Depends(get_db),
):
    """
    Soft delete a file by its file_id.
    """
    deleted = soft_delete_file(db, file_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    return FileDeleteResponse(
        file_id=file_id,
        deleted=True,
        message="File deleted successfully",
    )
