#!/usr/bin/env python3
"""xlsx 元数据固定化 — 消除 openpyxl 每次保存写入当前时间戳导致的二进制 diff。

根因：openpyxl writer/excel.py 在每次 save() 时无条件将 docProps/core.xml 的
`dcterms:modified` 写为当前时间（created 在设置后可保持，modified 不可控），
导致同一内容的 xlsx 重复生成后二进制不同——templates diff 抖动（第五轮审查 P2-1）。

方案：保存到内存 BytesIO → 重写 core.xml 的 created/modified 为固定时间戳 →
一次性覆写目标文件（不创建临时文件、不做 replace/remove，避免沙箱 hook 拦截）。
"""
import io
import re
import zipfile

FIXED_TS = "2026-01-01T00:00:00Z"


def _rewrite_core_xml(text):
    """将 core.xml 中的 created/modified 时间戳替换为固定值。"""
    text = re.sub(
        r"<dcterms:created[^>]*>[^<]*</dcterms:created>",
        '<dcterms:created xsi:type="dcterms:W3CDTF">%s</dcterms:created>' % FIXED_TS,
        text,
    )
    text = re.sub(
        r"<dcterms:modified[^>]*>[^<]*</dcterms:modified>",
        '<dcterms:modified xsi:type="dcterms:W3CDTF">%s</dcterms:modified>' % FIXED_TS,
        text,
    )
    return text


def save_frozen(wb, out_path):
    """保存工作簿并固定 core.xml 时间戳，生成结果可复现。

    全程在内存完成 zip 重建，仅最后一次直接写目标文件（openpyxl 原生
    save 行为一致），不依赖 os.replace / os.remove（沙箱环境可能拦截）。
    """
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    out = io.BytesIO()
    with zipfile.ZipFile(buf, "r") as zin, \
         zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "docProps/core.xml":
                data = _rewrite_core_xml(data.decode("utf-8")).encode("utf-8")
            zout.writestr(item, data)

    with open(out_path, "wb") as f:
        f.write(out.getvalue())
