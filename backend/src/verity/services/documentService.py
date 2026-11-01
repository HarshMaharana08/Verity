import logging
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from uuid import UUID, uuid4

from pypdf import PdfReader
from pypdf.errors import PyPdfError
from sqlalchemy.orm import Session

from sqlalchemy import select

from verity.models.investigation import Investigation
from verity.models.investigationDocument import (
    InvestigationDocument,
)


documentLogger = logging.getLogger(__name__)


class InvestigationNotFoundError(LookupError):
    pass


class InvalidDocumentError(RuntimeError):
    pass


class DocumentTooLargeError(RuntimeError):
    pass


class DocumentStorageError(RuntimeError):
    pass


def readAndValidatePdf(
    documentStream: BinaryIO,
    originalFileName: str | None,
    maxDocumentSizeBytes: int,
) -> tuple[str, bytes]:
    normalizedFileName = PurePosixPath(
        (originalFileName or "").replace("\\", "/")
    ).name.strip()

    if not normalizedFileName:
        raise InvalidDocumentError("A filename is required.")

    if len(normalizedFileName) > 255:
        raise InvalidDocumentError(
            "The filename must not exceed 255 characters."
        )

    if any(
        ord(character) < 32
        for character in normalizedFileName
    ):
        raise InvalidDocumentError(
            "The filename contains invalid characters."
        )

    if PurePosixPath(normalizedFileName).suffix.lower() != ".pdf":
        raise InvalidDocumentError("Only PDF files are accepted.")

    documentStream.seek(0)
    documentBytes = documentStream.read(
        maxDocumentSizeBytes + 1
    )

    if not documentBytes:
        raise InvalidDocumentError("The uploaded file is empty.")

    if len(documentBytes) > maxDocumentSizeBytes:
        raise DocumentTooLargeError(
            "The uploaded file exceeds the maximum allowed size."
        )

    if not documentBytes.startswith(b"%PDF-"):
        raise InvalidDocumentError(
            "The uploaded file does not have a valid PDF header."
        )

    try:
        with BytesIO(documentBytes) as pdfStream:
            pdfReader = PdfReader(
                pdfStream,
                strict=True,
            )

            if pdfReader.is_encrypted:
                raise InvalidDocumentError(
                    "Encrypted PDFs are not supported."
                )

            if len(pdfReader.pages) == 0:
                raise InvalidDocumentError(
                    "The PDF must contain at least one page."
                )

    except (PyPdfError, ValueError) as validationError:
        raise InvalidDocumentError(
            "The uploaded PDF could not be parsed."
        ) from validationError

    return normalizedFileName, documentBytes


def uploadInvestigationDocument(
    databaseSession: Session,
    investigationId: UUID,
    documentStream: BinaryIO,
    originalFileName: str | None,
    documentStorageRoot: Path,
    maxDocumentSizeBytes: int,
) -> InvestigationDocument:
    documentPath: Path | None = None
    documentFileCreated = False

    try:
        with databaseSession.begin():
            investigationRecord = databaseSession.get(
                Investigation,
                investigationId,
            )

            if investigationRecord is None:
                raise InvestigationNotFoundError(
                    "Investigation not found."
                )

            normalizedFileName, documentBytes = readAndValidatePdf(
                documentStream=documentStream,
                originalFileName=originalFileName,
                maxDocumentSizeBytes=maxDocumentSizeBytes,
            )

            documentId = uuid4()

            storageKey = (
                PurePosixPath("investigations")
                / str(investigationId)
                / f"{documentId}.pdf"
            )

            documentPath = documentStorageRoot.joinpath(
                *storageKey.parts
            )

            try:
                documentPath.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                with documentPath.open("xb") as storedDocument:
                    documentFileCreated = True
                    storedDocument.write(documentBytes)

            except OSError as storageError:
                raise DocumentStorageError(
                    "The document could not be stored."
                ) from storageError

            documentRecord = InvestigationDocument(
                documentId=documentId,
                investigationId=investigationId,
                originalFileName=normalizedFileName,
                storageKey=storageKey.as_posix(),
                mediaType="application/pdf",
                fileSizeBytes=len(documentBytes),
                sha256Digest=sha256(documentBytes).hexdigest(),
            )

            databaseSession.add(documentRecord)
            databaseSession.flush()
            databaseSession.refresh(documentRecord)

        return documentRecord

    except Exception:
        if documentFileCreated and documentPath is not None:
            try:
                documentPath.unlink(missing_ok=True)
            except OSError:
                documentLogger.exception(
                    "Failed to clean up document after upload failure."
                )

        raise
    
class DocumentNotFoundError(LookupError):
    pass


def listInvestigationDocuments(
    databaseSession: Session,
    investigationId: UUID,
    pageSize: int,
    pageOffset: int,
) -> tuple[list[InvestigationDocument], bool]:
    investigationRecord = databaseSession.get(
        Investigation,
        investigationId,
    )

    if investigationRecord is None:
        raise InvestigationNotFoundError(
            "Investigation not found."
        )

    documentQuery = (
        select(InvestigationDocument)
        .where(
            InvestigationDocument.investigationId
            == investigationId
        )
        .order_by(
            InvestigationDocument.uploadedAt.desc(),
            InvestigationDocument.documentId.desc(),
        )
        .offset(pageOffset)
        .limit(pageSize + 1)
    )

    documentRecords = list(
        databaseSession.scalars(documentQuery).all()
    )

    hasMore = len(documentRecords) > pageSize

    return documentRecords[:pageSize], hasMore


def getDocumentDownloadDetails(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    documentStorageRoot: Path,
) -> tuple[Path, str]:
    documentQuery = select(InvestigationDocument).where(
        InvestigationDocument.documentId == documentId,
        InvestigationDocument.investigationId == investigationId,
    )

    documentRecord = databaseSession.scalar(documentQuery)

    if documentRecord is None:
        raise DocumentNotFoundError(
            "Document not found for this investigation."
        )

    expectedStorageKey = (
        PurePosixPath("investigations")
        / str(investigationId)
        / f"{documentId}.pdf"
    )

    if documentRecord.storageKey != expectedStorageKey.as_posix():
        raise DocumentStorageError(
            "The document storage reference is invalid."
        )

    try:
        resolvedStorageRoot = documentStorageRoot.resolve()

        documentPath = resolvedStorageRoot.joinpath(
            *expectedStorageKey.parts
        ).resolve(strict=True)

        if not documentPath.is_relative_to(resolvedStorageRoot):
            raise DocumentStorageError(
                "The document path is outside document storage."
            )

        if not documentPath.is_file():
            raise DocumentStorageError(
                "The stored document is unavailable."
            )

    except (OSError, RuntimeError) as storageError:
        raise DocumentStorageError(
            "The stored document could not be accessed."
        ) from storageError

    return documentPath, documentRecord.originalFileName