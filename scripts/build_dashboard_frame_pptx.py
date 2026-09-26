"""Add implementation-oriented Dash wireframes to dashboard slides 12-14.

The source PPTX is kept unchanged. The generated deck places the existing
concept artwork on the left and a native PowerPoint Dash component frame on
the right so the team can agree on layout and component IDs before coding.
"""

from __future__ import annotations

import copy
import tempfile
import zipfile
from pathlib import Path

from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "2조_설비_고장_예측_기반_정비_의사결정_지원_시스템_final.pptx"
OUTPUT = ROOT / "docs" / "2조_설비_고장_예측_기반_정비_의사결정_지원_시스템_final_dash_frame.pptx"

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
P = f"{{{NS['p']}}}"
A = f"{{{NS['a']}}}"

# Slide coordinates use EMU. The deck is 18,288,000 x 10,287,000 (16:9).
BLUE = "2F80ED"
NAVY = "17324D"
PALE = "EEF5FD"
PALE_2 = "F7FAFE"
LINE = "9DBFE7"
TEXT = "18324A"
MUTED = "60758A"
WHITE = "FFFFFF"
GREEN = "DDF5EA"
ORANGE = "FFF0DC"
RED = "FDE6EA"
PURPLE = "EFE7FF"


def qn(prefix: str, tag: str) -> str:
    return f"{{{NS[prefix]}}}{tag}"


def max_shape_id(root: etree._Element) -> int:
    ids = [int(v) for v in root.xpath("//p:cNvPr/@id", namespaces=NS) if v.isdigit()]
    return max(ids, default=1)


def set_xfrm(node: etree._Element, x: int, y: int, cx: int, cy: int) -> None:
    xfrm = node.find(".//a:xfrm", NS)
    if xfrm is None:
        raise ValueError("Shape has no transform")
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    off.attrib.update({"x": str(x), "y": str(y)})
    ext.attrib.update({"cx": str(cx), "cy": str(cy)})


def remove_named_shapes(root: etree._Element, names: set[str]) -> None:
    sp_tree = root.find(".//p:spTree", NS)
    for node in list(sp_tree):
        props = node.find(".//p:cNvPr", NS)
        if props is not None and props.get("name") in names:
            sp_tree.remove(node)


def add_shape(
    sp_tree: etree._Element,
    shape_id: int,
    name: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    text: str = "",
    *,
    fill: str = WHITE,
    line: str = LINE,
    line_width: int = 12700,
    font_size: int = 1050,
    font_color: str = TEXT,
    bold: bool = False,
    align: str = "ctr",
    valign: str = "ctr",
    radius: bool = True,
    margin: int = 85000,
) -> etree._Element:
    sp = etree.SubElement(sp_tree, P + "sp")
    nv = etree.SubElement(sp, P + "nvSpPr")
    etree.SubElement(nv, P + "cNvPr", id=str(shape_id), name=name)
    etree.SubElement(nv, P + "cNvSpPr")
    etree.SubElement(nv, P + "nvPr")

    sp_pr = etree.SubElement(sp, P + "spPr")
    xfrm = etree.SubElement(sp_pr, A + "xfrm")
    etree.SubElement(xfrm, A + "off", x=str(x), y=str(y))
    etree.SubElement(xfrm, A + "ext", cx=str(cx), cy=str(cy))
    geom = etree.SubElement(sp_pr, A + "prstGeom", prst="roundRect" if radius else "rect")
    etree.SubElement(geom, A + "avLst")
    solid = etree.SubElement(sp_pr, A + "solidFill")
    etree.SubElement(solid, A + "srgbClr", val=fill)
    ln = etree.SubElement(sp_pr, A + "ln", w=str(line_width))
    ln_fill = etree.SubElement(ln, A + "solidFill")
    etree.SubElement(ln_fill, A + "srgbClr", val=line)

    tx = etree.SubElement(sp, P + "txBody")
    etree.SubElement(
        tx,
        A + "bodyPr",
        anchor=valign,
        lIns=str(margin),
        rIns=str(margin),
        tIns=str(margin // 2),
        bIns=str(margin // 2),
        wrap="square",
    )
    etree.SubElement(tx, A + "lstStyle")
    para = etree.SubElement(tx, A + "p")
    etree.SubElement(para, A + "pPr", algn=align)
    lines = text.split("\n") or [""]
    for index, value in enumerate(lines):
        if index:
            etree.SubElement(para, A + "br")
        run = etree.SubElement(para, A + "r")
        rpr = etree.SubElement(
            run,
            A + "rPr",
            lang="ko-KR",
            sz=str(font_size),
            b="1" if bold else "0",
        )
        fill_node = etree.SubElement(rpr, A + "solidFill")
        etree.SubElement(fill_node, A + "srgbClr", val=font_color)
        etree.SubElement(rpr, A + "latin", typeface="Aptos")
        etree.SubElement(rpr, A + "ea", typeface="맑은 고딕")
        etree.SubElement(run, A + "t").text = value
    etree.SubElement(para, A + "endParaRPr", lang="ko-KR", sz=str(font_size))
    return sp


def add_label(sp_tree, sid, text, x, y, cx, *, fill=BLUE, color=WHITE):
    return add_shape(
        sp_tree, sid, f"Dash label {sid}", x, y, cx, 350000, text,
        fill=fill, line=fill, font_size=1050, font_color=color, bold=True,
        radius=True, margin=40000,
    )


def add_divider(sp_tree, sid, x):
    return add_shape(
        sp_tree, sid, f"Divider {sid}", x, 1380000, 10000, 8350000, "",
        fill=LINE, line=LINE, line_width=0, radius=False, margin=0,
    )


def add_common_right_frame(sp_tree, sid, x, y, w, h, title):
    add_shape(sp_tree, sid, f"Dash outer frame {sid}", x, y, w, h, "", fill=WHITE, line=NAVY,
              line_width=22000, radius=True, margin=0)
    sid += 1
    add_shape(sp_tree, sid, f"Dash frame title {sid}", x + 120000, y + 90000, w - 240000, 420000,
              title, fill=NAVY, line=NAVY, font_size=1150, font_color=WHITE, bold=True,
              align="l", margin=110000)
    sid += 1
    add_shape(sp_tree, sid, f"Dash store {sid}", x + w - 2260000, y + 150000, 2080000, 290000,
              'dcc.Store(id="page-data")', fill=PURPLE, line="B79DEB", font_size=800,
              font_color="5C3A98", bold=True, margin=35000)
    return sid + 1


def build_main(root: etree._Element) -> None:
    sp_tree = root.find(".//p:spTree", NS)
    sid = max_shape_id(root) + 1
    pic = root.xpath("//p:pic[p:nvPicPr/p:cNvPr[@name='그림 7']]", namespaces=NS)[0]
    set_xfrm(pic, 500000, 1920000, 8250000, 5806831)

    add_label(sp_tree, sid, "기획 UI · 업무 우선순위 화면", 500000, 1430000, 3050000); sid += 1
    add_shape(sp_tree, sid, "Concept caption", 500000, 7900000, 8250000, 650000,
              "위험도 + 재고 + 조달 + 비용을 한 화면에서 확인\n※ 좌측 이미지는 목표 UI, 우측은 구현 전 Dash 뼈대",
              fill=PALE_2, line=LINE, font_size=900, font_color=MUTED, align="l", margin=100000); sid += 1
    add_divider(sp_tree, sid, 9000000); sid += 1
    add_label(sp_tree, sid, "Dash 프레임 · 메인 페이지", 9280000, 1430000, 2900000); sid += 1

    x, y, w, h = 9280000, 1900000, 8420000, 7350000
    sid = add_common_right_frame(sp_tree, sid, x, y, w, h, 'html.Div(id="main-page")')
    add_shape(sp_tree, sid, "Main sidebar", x + 150000, y + 650000, 1150000, 5750000,
              "Sidebar\n\n대시보드\n설비별 보기\n예측 분석\n재고 관리\n정비 이력\n통계 리포트",
              fill=NAVY, line=NAVY, font_size=800, font_color=WHITE, bold=True, margin=60000); sid += 1
    add_shape(sp_tree, sid, "Main filter", x + 150000, y + 6510000, 1150000, 570000,
              'dcc.DatePickerRange\nid="date-range"', fill=PALE, line=LINE, font_size=760, bold=True); sid += 1

    content_x = x + 1450000
    content_w = w - 1620000
    add_shape(sp_tree, sid, "Main KPI", content_x, y + 650000, content_w, 850000,
              'dbc.Row(id="kpi-row")  ·  KPI 카드 6개\n경고 설비 | 교체 임박 | 기한 초과 | 발주 필요 | 예상 손실 | 절감 효과',
              fill=PALE, line=BLUE, font_size=880, bold=True); sid += 1
    add_shape(sp_tree, sid, "Main calendar", content_x, y + 1650000, 4130000, 2600000,
              'html.Div(id="todo-calendar")\n월간 To-Do 캘린더\n발주 마감 · 교체 임박 · 정비 예정 · 기한 초과',
              fill=WHITE, line=LINE, font_size=900, bold=True); sid += 1
    add_shape(sp_tree, sid, "Main top5", content_x + 4300000, y + 1650000, content_w - 4300000, 2600000,
              'html.Div(id="priority-top5")\n우선 확인 설비 TOP 5\n재고위험 · 발주긴급 · 예상손실 · 대응여유',
              fill=RED, line="F2A8B5", font_size=860, bold=True); sid += 1
    add_shape(sp_tree, sid, "Main alerts", content_x, y + 4400000, 2050000, 1150000,
              'dcc.Graph(id="probability-jump")\n확률 급상승 TOP 3', fill=ORANGE, line="F3BE75", font_size=820, bold=True); sid += 1
    add_shape(sp_tree, sid, "Main stock", content_x + 2200000, y + 4400000, 2050000, 1150000,
              'dash_table.DataTable\nid="stock-risk-table"\n재고 × 위험 교차', fill=GREEN, line="88D3B3", font_size=790, bold=True); sid += 1
    add_shape(sp_tree, sid, "Main response", content_x + 4400000, y + 4400000, content_w - 4400000, 1150000,
              'dcc.Graph(id="response-rate")\n과거 대응률 추이', fill=PALE, line=LINE, font_size=820, bold=True); sid += 1
    add_shape(sp_tree, sid, "Main callback", content_x, y + 5750000, content_w, 660000,
              'Callback 흐름  date-range / selected-machine → page-data → KPI · Calendar · Top5 · Graph',
              fill=PURPLE, line="B79DEB", font_size=760, font_color="5C3A98", bold=True, align="l", margin=90000)


def build_detail(root: etree._Element) -> None:
    sp_tree = root.find(".//p:spTree", NS)
    sid = max_shape_id(root) + 1
    pic = root.xpath("//p:pic[p:nvPicPr/p:cNvPr[@name='그림 21']]", namespaces=NS)[0]
    set_xfrm(pic, 700000, 1550000, 5100000, 7361947)

    add_label(sp_tree, sid, "기획 UI · 설비별 상세", 700000, 1210000, 2600000); sid += 1
    add_shape(sp_tree, sid, "Detail concept caption", 700000, 9020000, 5100000, 570000,
              "부품 위험 → 근거 센서 → 비용 최소 발주 → 조치 이력",
              fill=PALE_2, line=LINE, font_size=850, font_color=MUTED, bold=True); sid += 1
    add_divider(sp_tree, sid, 6000000); sid += 1
    add_label(sp_tree, sid, "Dash 프레임 · 설비 상세 페이지", 6280000, 1430000, 3350000); sid += 1

    x, y, w, h = 6280000, 1900000, 11420000, 7350000
    sid = add_common_right_frame(sp_tree, sid, x, y, w, h, 'html.Div(id="equipment-detail-page")')
    add_shape(sp_tree, sid, "Detail sidebar", x + 150000, y + 650000, 1150000, 5750000,
              "Sidebar\n\n설비 검색\n전체 설비\nM-023\nM-055\nM-071\nM-087\nM-102",
              fill=NAVY, line=NAVY, font_size=810, font_color=WHITE, bold=True, margin=60000); sid += 1
    add_shape(sp_tree, sid, "Detail selector", x + 150000, y + 6510000, 1150000, 570000,
              'dcc.Dropdown\nid="machine-id"', fill=PALE, line=LINE, font_size=760, bold=True); sid += 1

    cx = x + 1450000
    cw = w - 1620000
    add_shape(sp_tree, sid, "Detail header", cx, y + 650000, cw, 650000,
              'html.Div(id="equipment-summary")  설비명 · 종합진단 · 예상 고장 시기 · 예측 신뢰도',
              fill=PALE, line=BLUE, font_size=860, bold=True, align="l", margin=100000); sid += 1
    add_shape(sp_tree, sid, "Detail schematic", cx, y + 1450000, 3650000, 2450000,
              'html.Div(id="machine-map")\n설비 이미지 + 부품 위험 배지\nComp1~4 확률 · 예상 시기',
              fill=WHITE, line=LINE, font_size=900, bold=True); sid += 1
    add_shape(sp_tree, sid, "Detail sensors", cx + 3820000, y + 1450000, cw - 3820000, 2450000,
              'dcc.Graph(id="sensor-trend")\n센서 추이 · IF · 3-Sigma · IQR\nhtml.Div(id="risk-reason")  위험 판단 근거',
              fill=ORANGE, line="F3BE75", font_size=840, bold=True); sid += 1
    add_shape(sp_tree, sid, "Detail cost", cx, y + 4100000, 3000000, 1350000,
              'dcc.Graph(id="order-cost-curve")\n비용 최소 발주 시점', fill=GREEN, line="88D3B3", font_size=820, bold=True); sid += 1
    add_shape(sp_tree, sid, "Detail order", cx + 3170000, y + 4100000, 2600000, 1350000,
              'html.Div(id="order-summary")\n마감 D-day · 권장 수량\n조달기간 · 대응 여유', fill=PALE, line=LINE, font_size=800, bold=True); sid += 1
    add_shape(sp_tree, sid, "Detail scenarios", cx + 5940000, y + 4100000, cw - 5940000, 1350000,
              'dbc.CardGroup(id="scenario-cards")\n오늘 발주 | 1주 대기 | 2주 대기', fill=PURPLE, line="B79DEB", font_size=800,
              font_color="5C3A98", bold=True); sid += 1
    add_shape(sp_tree, sid, "Detail supplier", cx, y + 5650000, 3000000, 670000,
              'html.Div(id="supplier-contact")  협력사 정보', fill=WHITE, line=LINE,
              font_size=760, bold=True); sid += 1
    add_shape(sp_tree, sid, "Detail history", cx + 3170000, y + 5650000, cw - 3170000, 670000,
              'dash_table.DataTable(id="maintenance-history")  교체·조치 이력', fill=WHITE, line=LINE,
              font_size=760, bold=True); sid += 1
    add_shape(sp_tree, sid, "Detail callback", cx, y + 6480000, cw, 450000,
              'Callback  machine-id / component → sensor-trend · cost curve · order summary · history',
              fill=PURPLE, line="B79DEB", font_size=720, font_color="5C3A98", bold=True,
              align="l", margin=85000)


def build_stats(root: etree._Element) -> None:
    sp_tree = root.find(".//p:spTree", NS)
    remove_named_shapes(root, {
        "직사각형 2", "직사각형 5", "직사각형 4", "직사각형 14", "직사각형 15",
        "모서리가 둥근 직사각형 7", "모서리가 둥근 직사각형 24",
        "Google Shape;135;p3",
    })
    sid = max_shape_id(root) + 1
    pics = root.xpath("//p:pic", namespaces=NS)
    by_name = {pic.find(".//p:cNvPr", NS).get("name"): pic for pic in pics}
    set_xfrm(by_name["그림 9"], 500000, 2550000, 3970000, 2977500)
    set_xfrm(by_name["그림 16"], 4700000, 2550000, 3970000, 2977500)

    add_label(sp_tree, sid, "기획 UI · 위험 히트맵", 500000, 1430000, 2600000); sid += 1
    add_shape(sp_tree, sid, "Stats F10 label", 500000, 2060000, 3970000, 360000,
              "F10 · 이상 위험 (3-Sigma + IF)", fill=ORANGE, line="F3BE75", font_size=830, bold=True); sid += 1
    add_shape(sp_tree, sid, "Stats F09 label", 4700000, 2060000, 3970000, 360000,
              "F09 · 고장 위험", fill=RED, line="F2A8B5", font_size=830, bold=True); sid += 1
    add_shape(sp_tree, sid, "Stats concept caption", 500000, 5750000, 8170000, 1050000,
              "같은 100개 대상을 두 위험 관점으로 비교\n녹색 → 노란색 → 빨간색 순으로 우선 점검 대상 식별",
              fill=PALE_2, line=LINE, font_size=900, font_color=MUTED, bold=True); sid += 1
    add_shape(sp_tree, sid, "Stats decision rule", 500000, 6950000, 8170000, 1250000,
              "교차 해석\n고장↑ 이상↑ 즉시 점검  |  고장↓ 이상↑ 신규 전조 검토\n고장↑ 이상↓ 이력·교체주기 검토  |  둘 다 낮음 모니터링",
              fill=PALE, line=BLUE, font_size=820, bold=True); sid += 1
    add_divider(sp_tree, sid, 9000000); sid += 1
    add_label(sp_tree, sid, "Dash 프레임 · 통계 페이지", 9280000, 1430000, 2900000); sid += 1

    x, y, w, h = 9280000, 1900000, 8420000, 7350000
    sid = add_common_right_frame(sp_tree, sid, x, y, w, h, 'html.Div(id="statistics-page")')
    add_shape(sp_tree, sid, "Stats filters", x + 150000, y + 650000, w - 300000, 720000,
              'dbc.Row(id="statistics-filters")  기간 dcc.DatePickerRange  |  대상 Dropdown  |  탐지방법 Dropdown',
              fill=PALE, line=BLUE, font_size=810, bold=True, align="l", margin=100000); sid += 1
    add_shape(sp_tree, sid, "Stats tabs", x + 150000, y + 1530000, w - 300000, 550000,
              'dcc.Tabs(id="risk-tabs")   [ F09 고장 위험 ]   [ F10 이상 위험 ]',
              fill=NAVY, line=NAVY, font_size=900, font_color=WHITE, bold=True); sid += 1
    add_shape(sp_tree, sid, "Stats heatmap", x + 150000, y + 2250000, 5450000, 3000000,
              'dcc.Graph(id="risk-heatmap")\nPlotly Heatmap\nx=설비/라인 · y=부품/공정\ncolor=위험도 · clickData=선택 대상',
              fill=WHITE, line=LINE, font_size=930, bold=True); sid += 1
    add_shape(sp_tree, sid, "Stats detail", x + 5800000, y + 2250000, w - 5950000, 1450000,
              'html.Div(id="selected-risk-detail")\n선택 대상 · 점수 · 순위\n주요 근거 · 최근 변화',
              fill=RED, line="F2A8B5", font_size=800, bold=True); sid += 1
    add_shape(sp_tree, sid, "Stats legend", x + 5800000, y + 3850000, w - 5950000, 1400000,
              'html.Div(id="risk-legend")\n낮음  ━  중간  ━  높음\n임계값 · 산정 기준 표시',
              fill=GREEN, line="88D3B3", font_size=800, bold=True); sid += 1
    add_shape(sp_tree, sid, "Stats table", x + 150000, y + 5450000, w - 300000, 900000,
              'dash_table.DataTable(id="risk-ranking")  순위 | 대상 | 고장위험 | 이상위험 | 상태 | 상세 이동',
              fill=PALE_2, line=LINE, font_size=760, bold=True); sid += 1
    add_shape(sp_tree, sid, "Stats callback", x + 150000, y + 6530000, w - 300000, 450000,
              'Callback  filters / risk-tabs → risk-heatmap · ranking  |  heatmap.clickData → detail',
              fill=PURPLE, line="B79DEB", font_size=720, font_color="5C3A98", bold=True,
              align="l", margin=85000)


def update_slide(xml_bytes: bytes, slide_number: int) -> bytes:
    root = etree.fromstring(xml_bytes)
    if slide_number == 12:
        build_main(root)
    elif slide_number == 13:
        build_detail(root)
    elif slide_number == 14:
        build_stats(root)
    else:
        raise ValueError(slide_number)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def main() -> None:
    replacements = {}
    with zipfile.ZipFile(SOURCE, "r") as source_zip:
        for slide_number in (12, 13, 14):
            name = f"ppt/slides/slide{slide_number}.xml"
            replacements[name] = update_slide(source_zip.read(name), slide_number)

        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx", dir=OUTPUT.parent) as stream:
            temporary = Path(stream.name)
        try:
            with zipfile.ZipFile(temporary, "w") as output_zip:
                for info in source_zip.infolist():
                    data = replacements.get(info.filename, source_zip.read(info.filename))
                    output_zip.writestr(copy.copy(info), data)
            temporary.replace(OUTPUT)
        finally:
            temporary.unlink(missing_ok=True)

    with zipfile.ZipFile(OUTPUT, "r") as check_zip:
        bad = check_zip.testzip()
        if bad:
            raise RuntimeError(f"Corrupt ZIP member: {bad}")
        for slide_number in (12, 13, 14):
            etree.fromstring(check_zip.read(f"ppt/slides/slide{slide_number}.xml"))
    print(OUTPUT)


if __name__ == "__main__":
    main()
