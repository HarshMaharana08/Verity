import logging
from typing import Annotated
from uuid import UUID

from fastapi.responses import FileResponse

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from verity.databaseSession import getDatabaseSession

from verity.schemas.documentSchemas import (
    DocumentListResponse,
    DocumentResponse,
)

from verity.services.documentService import (
    DocumentNotFoundError,
    DocumentStorageError,
    DocumentTooLargeError,
    InvalidDocumentError,
    InvestigationNotFoundError,
    getDocumentDownloadDetails,
    listInvestigationDocuments,
    uploadInvestigationDocument,
)


documentLogger = logging.getLogger(__name__)

documentRouter = APIRouter(
    prefix="/investigations",
    tags=["Documents"],
)


@documentRouter.post(
    "/{investigationId}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an investigation PDF",
    responses={
        400: {"description": "Invalid or unsupported PDF"},
        404: {"description": "Investigation not found"},
        413: {"description": "Document exceeds the size limit"},
        500: {"description": "Document could not be saved"},
    },
)
def uploadInvestigationDocumentEndpoint(
    investigationId: UUID,
    request: Request,
    documentFile: Annotated[
        UploadFile,
        File(description="Incident-report PDF, maximum 10 MiB"),
    ],
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> DocumentResponse:
    try:
        documentRecord = uploadInvestigationDocument(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentStream=documentFile.file,
            originalFileName=documentFile.filename,
            documentStorageRoot=(
                request.app.state.documentStorageRoot
            ),
            maxDocumentSizeBytes=(
                request.app.state.maxDocumentSizeBytes
            ),
        )

    except InvestigationNotFoundError as uploadError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(uploadError),
        ) from None

    except DocumentTooLargeError as uploadError:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(uploadError),
        ) from None

    except InvalidDocumentError as uploadError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(uploadError),
        ) from None

    except (DocumentStorageError, SQLAlchemyError):
        documentLogger.exception("Document upload failed.")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The document could not be saved.",
        ) from None

    return DocumentResponse.model_validate(documentRecord)


@documentRouter.get(
    "/{investigationId}/documents",
    response_model=DocumentListResponse,
    summary="List documents for an investigation",
    responses={
        404: {"description": "Investigation not found"},
    },
)
def listInvestigationDocumentsEndpoint(
    investigationId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
    pageSize: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 20,
    pageOffset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> DocumentListResponse:
    try:
        documentRecords, hasMore = listInvestigationDocuments(
            databaseSession=databaseSession,
            investigationId=investigationId,
            pageSize=pageSize,
            pageOffset=pageOffset,
        )

    except InvestigationNotFoundError as documentError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(documentError),
        ) from None

    documentItems = [
        DocumentResponse.model_validate(documentRecord)
        for documentRecord in documentRecords
    ]

    return DocumentListResponse(
        items=documentItems,
        pageSize=pageSize,
        pageOffset=pageOffset,
        hasMore=hasMore,
    )
    
    
@documentRouter.get(
    "/{investigationId}/documents/{documentId}/download",
    response_class=FileResponse,
    summary="Download an investigation document",
    responses={
        200: {
            "description": "PDF document",
            "content": {
                "application/pdf": {
                    "schema": {
                        "type": "string",
                        "format": "binary",
                    },
                },
            },
        },
        404: {"description": "Document not found"},
        500: {"description": "Stored document unavailable"},
    },
)
def downloadInvestigationDocumentEndpoint(
    investigationId: UUID,
    documentId: UUID,
    request: Request,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> FileResponse:
    try:
        documentPath, originalFileName = getDocumentDownloadDetails(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            documentStorageRoot=(
                request.app.state.documentStorageRoot
            ),
        )

    except DocumentNotFoundError as documentError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(documentError),
        ) from None

    except (DocumentStorageError, SQLAlchemyError):
        documentLogger.exception(
            "Document download preparation failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The document could not be retrieved.",
        ) from None

    return FileResponse(
        path=documentPath,
        media_type="application/pdf",
        filename=originalFileName,
        content_disposition_type="attachment",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )