from __future__ import annotations

import csv
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "model3" / "evaluation"
CSV_PATH = OUT_DIR / "model_failure_comparison.csv"
IMAGE_PATH = OUT_DIR / "model_failure_comparison.png"
DOCX_PATH = OUT_DIR / "REPORT.docx"

NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'
)


def run_properties(size=20, bold=False, color="000000") -> str:
    bold_xml = "<w:b/>" if bold else ""
    return (
        "<w:rPr>"
        '<w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" '
        'w:eastAsia="Malgun Gothic"/>'
        f"{bold_xml}<w:color w:val=\"{color}\"/><w:sz w:val=\"{size}\"/>"
        f"<w:szCs w:val=\"{size}\"/></w:rPr>"
    )


def paragraph(
    text: str,
    *,
    style: str | None = None,
    bold=False,
    size=20,
    color="000000",
    align=None,
    before=0,
    after=80,
    line=240,
    keep_next=False,
) -> str:
    ppr = []
    if style:
        ppr.append(f'<w:pStyle w:val="{style}"/>')
    if align:
        ppr.append(f'<w:jc w:val="{align}"/>')
    if keep_next:
        ppr.append("<w:keepNext/>")
    ppr.append(
        f'<w:spacing w:before="{before}" w:after="{after}" w:line="{line}" '
        'w:lineRule="auto"/>'
    )
    return (
        "<w:p><w:pPr>" + "".join(ppr) + "</w:pPr><w:r>"
        + run_properties(size=size, bold=bold, color=color)
        + f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'
    )


def cell(text: str, width: int, *, header=False, shade=None) -> str:
    fill = "1F4E78" if header else shade
    tcpr = [f'<w:tcW w:w="{width}" w:type="dxa"/>', '<w:vAlign w:val="center"/>']
    if fill:
        tcpr.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>')
    tcpr.append(
        '<w:tcMar><w:top w:w="45" w:type="dxa"/><w:left w:w="45" w:type="dxa"/>'
        '<w:bottom w:w="45" w:type="dxa"/><w:right w:w="45" w:type="dxa"/></w:tcMar>'
    )
    color = "FFFFFF" if header else "000000"
    text_xml = paragraph(
        text,
        bold=header,
        size=16,
        color=color,
        align="center",
        after=0,
        line=205,
    )
    return f'<w:tc><w:tcPr>{"".join(tcpr)}</w:tcPr>{text_xml}</w:tc>'


def results_table(rows: list[dict[str, str]]) -> str:
    headers = ["모델", "구간", "탐지율", "적중률", "오경보율", "선행시간", "Lift"]
    widths = [2050, 700, 1050, 1050, 1150, 1150, 850]
    table_rows = [
        "<w:tr><w:trPr><w:tblHeader/></w:trPr>"
        + "".join(cell(value, width, header=True) for value, width in zip(headers, widths))
        + "</w:tr>"
    ]
    for idx, row in enumerate(rows):
        shade = "EAF2F8" if idx % 2 else None
        values = [
            row["model"],
            f'{int(row["horizon_hours"])}h',
            f'{float(row["failure_detection_rate"]):.1%}',
            f'{float(row["alert_precision"]):.1%}',
            f'{float(row["false_alert_rate"]):.1%}',
            f'{float(row["mean_lead_time_hours"]):.1f}h',
            f'{float(row["lift"]):.2f}',
        ]
        table_rows.append(
            "<w:tr>"
            + "".join(cell(value, width, shade=shade) for value, width in zip(values, widths))
            + "</w:tr>"
        )
    borders = "".join(
        f'<w:{edge} w:val="single" w:sz="4" w:space="0" w:color="D9D9D9"/>'
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV")
    )
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for width in widths)
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="8000" w:type="dxa"/>'
        '<w:tblLayout w:type="fixed"/><w:jc w:val="center"/>'
        f"<w:tblBorders>{borders}</w:tblBorders></w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>{''.join(table_rows)}</w:tbl>"
    )


def image_paragraph() -> str:
    width_emu = 5_943_600  # 6.5 in
    height_emu = 3_496_235
    return f"""
    <w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="80" w:after="70"/></w:pPr>
      <w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">
        <wp:extent cx="{width_emu}" cy="{height_emu}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>
        <wp:docPr id="1" name="모델 비교 그래프" descr="Isolation Forest 3 Sigma IQR 고장 예측 성능 비교"/>
        <wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>
        <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
          <pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="model_failure_comparison.png"/>
          <pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="rId1"/>
          <a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr>
          <a:xfrm><a:off x="0" y="0"/><a:ext cx="{width_emu}" cy="{height_emu}"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>
        </a:graphicData></a:graphic>
      </wp:inline></w:drawing></w:r>
    </w:p>
    """


def build_document(rows: list[dict[str, str]]) -> str:
    body = [
        paragraph("이상 탐지 모델 비교 결과", style="Title", size=34, bold=True, align="center", after=100),
        paragraph(
            "Isolation Forest는 경고 신뢰도가 가장 높고 3-Sigma는 탐지율과 경고 부담의 균형이 좋다. "
            "IQR은 고장 누락이 가장 적지만 오경보가 가장 많다.",
            size=20,
            after=70,
        ),
        paragraph(
            "대상  테스트 173,800건  실제 고장 140건  평가 구간  고장 전 24시간 48시간 72시간",
            size=17,
            color="555555",
            after=90,
        ),
        paragraph("핵심 결과", style="Heading1", size=23, bold=True, before=40, after=55, keep_next=True),
        results_table(rows),
        paragraph("비교 시각화", style="Heading1", size=23, bold=True, before=90, after=20, keep_next=True),
        image_paragraph(),
        paragraph("운영 판단", style="Heading1", size=23, bold=True, before=20, after=35, keep_next=True),
        paragraph("• 경고 신뢰도와 적은 이벤트 수가 중요하면 Isolation Forest가 적합하다.", size=18, after=20),
        paragraph("• 탐지율과 경고 부담의 균형이 필요하면 3-Sigma가 적합하다.", size=18, after=20),
        paragraph("• 고장 누락 최소화가 최우선이면 IQR이 적합하다.", size=18, after=35),
        paragraph(
            "오경보율이 모든 방식에서 80% 이상이므로 실제 적용 전 경고 병합 간격과 임계값 조정이 필요하다. "
            "고장 기록은 센서 이상 정답이 아니라 이후 운영 결과이므로 본 결과는 고장 사전 경고의 유용성을 평가한다.",
            size=16,
            color="555555",
            after=0,
            line=220,
        ),
    ]
    sect = (
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="576" w:right="648" w:bottom="576" w:left="648" '
        'w:header="360" w:footer="360" w:gutter="0"/>'
        '<w:cols w:space="720"/><w:docGrid w:linePitch="360"/></w:sectPr>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document {NS}><w:body>{"".join(body)}{sect}</w:body></w:document>'
    )


STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:eastAsia="Malgun Gothic"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="80" w:line="240" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:jc w:val="center"/></w:pPr><w:rPr><w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:eastAsia="Malgun Gothic"/><w:b/><w:color w:val="000000"/><w:sz w:val="34"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:eastAsia="Malgun Gothic"/><w:b/><w:color w:val="000000"/><w:sz w:val="23"/></w:rPr></w:style>
</w:styles>"""


def create_docx() -> None:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    package_dir = ROOT / ".tmp" / "report_docx_package"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    (package_dir / "_rels").mkdir(parents=True)
    (package_dir / "docProps").mkdir()
    (package_dir / "word" / "_rels").mkdir(parents=True)
    (package_dir / "word" / "media").mkdir()

    files = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>""",
        "word/document.xml": build_document(rows),
        "word/styles.xml": STYLES_XML,
        "word/_rels/document.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>""",
        "docProps/app.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Codex</Application></Properties>""",
        "docProps/core.xml": f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>이상 탐지 모델 비교 결과</dc:title><dc:creator>Codex</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">{datetime.now(timezone.utc).isoformat()}</dcterms:created></cp:coreProperties>""",
    }
    for relative, content in files.items():
        target = package_dir / relative
        target.write_text(content, encoding="utf-8")
    shutil.copyfile(IMAGE_PATH, package_dir / "word" / "media" / "image1.png")

    with zipfile.ZipFile(DOCX_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in package_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(package_dir).as_posix())
    print(DOCX_PATH)


if __name__ == "__main__":
    create_docx()
