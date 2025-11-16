"""
Unit tests for DocumentParser Excel/Word parsing.
"""
from io import BytesIO

import pytest

from apex.services.document_parser import DocumentParser


@pytest.fixture
def parser():
    return DocumentParser()


@pytest.mark.asyncio
async def test_parse_excel_extracts_sheets(parser):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Test Sheet"
    ws["A1"] = "Header 1"
    ws["B1"] = "Header 2"
    ws["A2"] = "Value 1"
    ws["B2"] = "Value 2"

    excel_bytes = BytesIO()
    wb.save(excel_bytes)
    excel_bytes.seek(0)

    result = await parser._parse_excel(excel_bytes.read(), "test.xlsx")

    assert result["filename"] == "test.xlsx"
    assert len(result["sheets"]) == 1
    assert result["sheets"][0]["name"] == "Test Sheet"
    assert result["sheets"][0]["rows"][1][0] == "Value 1"


@pytest.mark.asyncio
async def test_parse_word_extracts_paragraphs(parser):
    import docx

    doc = docx.Document()
    doc.add_paragraph("Test paragraph 1")
    doc.add_paragraph("Test paragraph 2")

    word_bytes = BytesIO()
    doc.save(word_bytes)
    word_bytes.seek(0)

    result = await parser._parse_word(word_bytes.read(), "test.docx")

    assert result["filename"] == "test.docx"
    assert len(result["paragraphs"]) == 2
    assert result["paragraphs"][0]["text"] == "Test paragraph 1"
