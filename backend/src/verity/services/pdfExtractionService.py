from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfTextExtractionError(Exception):
    pass


def extractPdfText(
    documentPath: Path,
    maxPages: int = 200,
    maxTextCharacters: int = 1_000_000,
) -> str:
    if maxPages < 1 or maxTextCharacters < 1:
        raise ValueError("Extraction limits must be positive.")

    try:
        with documentPath.open("rb") as documentStream:
            pdfReader = PdfReader(documentStream)

            if pdfReader.is_encrypted:
                raise PdfTextExtractionError(
                    "Encrypted PDFs are not supported."
                )

            pageCount = len(pdfReader.pages)

            if pageCount == 0:
                raise PdfTextExtractionError(
                    "The PDF contains no pages."
                )

            if pageCount > maxPages:
                raise PdfTextExtractionError(
                    f"The PDF exceeds the {maxPages}-page limit."
                )

            pageTexts: list[str] = []
            totalCharacters = 0

            for page in pdfReader.pages:
                pageText = page.extract_text() or ""

                # PostgreSQL text values cannot contain NUL.
                pageText = pageText.replace("\x00", "\ufffd")

                separatorLength = 2 if pageTexts else 0
                totalCharacters += (
                    len(pageText) + separatorLength
                )

                if totalCharacters > maxTextCharacters:
                    raise PdfTextExtractionError(
                        "Extracted text exceeds the "
                        f"{maxTextCharacters}-character limit."
                    )

                pageTexts.append(pageText)

    except (PdfReadError, OSError, ValueError) as extractionError:
        raise PdfTextExtractionError(
            "The PDF could not be read for text extraction."
        ) from extractionError

    extractedText = "\n\n".join(pageTexts).strip()

    if not extractedText:
        raise PdfTextExtractionError(
            "No extractable text was found. "
            "The PDF may require OCR."
        )

    return extractedText