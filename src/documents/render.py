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


def convert_docx_to_pdf(docx_path: Path, output_dir: Path, *, timeout: int = 60) -> Path | None:
    system = platform.system()
    logger.info("PDF conversion started. system=%s docx=%s outdir=%s", system, docx_path, output_dir)

    if system == "Linux":
        libreoffice = shutil.which("libreoffice") or shutil.which("soffice")
        if not libreoffice:
            logger.warning("LibreOffice not found in PATH; PDF conversion is unavailable on Linux.")
            return None

        command = [
            libreoffice,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(docx_path),
        ]
        logger.info("Running PDF conversion command: %s", " ".join(command))
        try:
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            logger.error("LibreOffice conversion timed out after %s seconds.", timeout)
            logger.error("LibreOffice stdout: %s", (exc.stdout or b"").decode(errors="ignore"))
            logger.error("LibreOffice stderr: %s", (exc.stderr or b"").decode(errors="ignore"))
            return None
        except subprocess.CalledProcessError as exc:
            logger.error("LibreOffice conversion failed with exit code %s.", exc.returncode)
            logger.error("LibreOffice stdout: %s", (exc.stdout or b"").decode(errors="ignore"))
            logger.error("LibreOffice stderr: %s", (exc.stderr or b"").decode(errors="ignore"))
            return None

        expected_pdf = output_dir / f"{docx_path.stem}.pdf"
        if expected_pdf.exists():
            return expected_pdf
        logger.error("LibreOffice finished but PDF not found at %s", expected_pdf)
        return None

    try:
        convert(str(docx_path), str(output_dir / f"{docx_path.stem}.pdf"))
    except Exception:  # noqa: BLE001 - external conversion can fail
        logger.exception("docx2pdf conversion failed.")
        return None

    output_pdf = output_dir / f"{docx_path.stem}.pdf"
    if output_pdf.exists():
        return output_pdf
    logger.error("docx2pdf finished but PDF not found at %s", output_pdf)
    return None


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
    pdf_result = convert_docx_to_pdf(docx_path, Path(temp_dir.name))
    if pdf_result is None:
        error = "PDF conversion failed."

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
