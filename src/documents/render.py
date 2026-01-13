from __future__ import annotations

from dataclasses import dataclass
import logging
import platform
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
import shutil
import subprocess

from docx2pdf import convert
from docxtpl import DocxTemplate

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
logger = logging.getLogger(__name__)


def convert_docx_to_pdf(docx_path: Path, *, timeout: int = 120) -> Path:
    system = platform.system().lower()
    output_dir = docx_path.parent
    logger.info("PDF conversion started. os=%s docx=%s outdir=%s", system, docx_path, output_dir)

    if system == "linux":
        libreoffice = shutil.which("libreoffice") or shutil.which("soffice")
        if not libreoffice:
            message = "LibreOffice not found in PATH; PDF conversion is unavailable on Linux."
            logger.error(message)
            raise RuntimeError(message)

        command = [
            libreoffice,
            "--headless",
            "--nologo",
            "--nolockcheck",
            "--norestore",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(docx_path),
        ]
        logger.info("Running PDF conversion command: %s", " ".join(command))
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            logger.error("LibreOffice conversion timed out after %s seconds.", timeout)
            logger.error("LibreOffice stdout: %s", exc.stdout or "")
            logger.error("LibreOffice stderr: %s", exc.stderr or "")
            raise RuntimeError("LibreOffice conversion timed out.") from exc
        except subprocess.CalledProcessError as exc:
            logger.error("LibreOffice conversion failed with exit code %s.", exc.returncode)
            logger.error("LibreOffice stdout: %s", exc.stdout or "")
            logger.error("LibreOffice stderr: %s", exc.stderr or "")
            raise RuntimeError("LibreOffice conversion failed.") from exc

        logger.info("LibreOffice stdout: %s", result.stdout or "")
        logger.info("LibreOffice stderr: %s", result.stderr or "")

        expected_pdf = docx_path.with_suffix(".pdf")
        if expected_pdf.exists():
            logger.info("PDF conversion finished. pdf=%s", expected_pdf)
            return expected_pdf
        message = f"LibreOffice finished but PDF not found at {expected_pdf}"
        logger.error(message)
        raise RuntimeError(message)

    try:
        convert(str(docx_path), str(docx_path.with_suffix(".pdf")))
    except Exception as exc:  # noqa: BLE001 - external conversion can fail
        logger.exception("docx2pdf conversion failed.")
        raise RuntimeError("docx2pdf conversion failed.") from exc

    output_pdf = docx_path.with_suffix(".pdf")
    if output_pdf.exists():
        logger.info("PDF conversion finished. pdf=%s", output_pdf)
        return output_pdf
    message = f"docx2pdf finished but PDF not found at {output_pdf}"
    logger.error(message)
    raise RuntimeError(message)


@dataclass
class RenderResult:
    docx_path: Path
    pdf_path: Path | None
    error: str | None
    _temp_dir: TemporaryDirectory

    def cleanup(self) -> None:
        self._temp_dir.cleanup()


def _render_docx(template_name: str, context: dict[str, Any], output_name: str) -> RenderResult:
    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    temp_dir = TemporaryDirectory()
    docx_path = Path(temp_dir.name) / f"{output_name}.docx"
    doc = DocxTemplate(str(template_path))
    doc.render(context)
    doc.save(str(docx_path))

    error: str | None = None
    pdf_result: Path | None = None
    try:
        pdf_result = convert_docx_to_pdf(docx_path)
    except Exception as exc:  # noqa: BLE001 - needed for user-facing errors
        logger.exception("PDF conversion failed.")
        error = str(exc)

    return RenderResult(docx_path=docx_path, pdf_path=pdf_result, error=error, _temp_dir=temp_dir)


def build_contract_context(data: dict[str, Any]) -> dict[str, Any]:
    end_date_value = data.get("end_date") or ""
    if end_date_value.lower() in {"не требуется", "нет"}:
        end_date_value = ""

    return {
        "CLIENT_NAME": data.get("client_name", ""),
        "CLIENT_MOBILE": data.get("phone", ""),
        "ADDRESS_DOG": data.get("address", ""),
        "DATE_DOG": data.get("contract_date", ""),
        "DATE_BEGIN": data.get("start_date", ""),
        "DATE_END": end_date_value,
        "TOTAL_SUM": data.get("total_sum", ""),
        "PASSPORT_SERIES": data.get("passport_series", ""),
        "PASSPORT_NUMBER": data.get("passport_number", ""),
        "PASSPORT_BASE": data.get("passport_base", ""),
        "PRE_PAY": data.get("pre_pay", ""),
        "FIRST_PAY": data.get("first_pay", ""),
        "SECOND_PAY": data.get("second_pay", ""),
    }


def build_act_context(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "DATE_DOG": data.get("contract_date", ""),
        "ADDRESS_DOG": data.get("address", ""),
        "CLIENT_NAME": data.get("client_name", ""),
        "PASSPORT_SERIES": data.get("passport_series", ""),
        "PASSPORT_NUMBER": data.get("passport_number", ""),
        "PASSPORT_BASE": data.get("passport_base", ""),
        "CLIENT_MOBILE": data.get("phone", ""),
    }


def build_supplement_context(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "CONTRACT_NUMBER": data.get("contract_number", ""),
        "SUPPLEMENT_DATE": data.get("supplement_date", ""),
        "SUPPLEMENT_TEXT": data.get("supplement_text", ""),
    }


def render_contract(data: dict[str, Any]) -> RenderResult:
    context = build_contract_context(data)
    return _render_docx("contract.docx", context, "contract")


def render_act(data: dict[str, Any]) -> RenderResult:
    context = build_act_context(data)
    return _render_docx("act.docx", context, "act")


def render_supplement(data: dict[str, Any]) -> RenderResult:
    context = build_supplement_context(data)
    return _render_docx("supplement.docx", context, "supplement")
