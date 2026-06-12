"""
本地分类层 — 平台只负责给全量数据,系列/品类/错标全在本地判定

为什么放本地而不是用平台搜索:
  · 卖家标题不写季号("AW03"),平台全文搜索会漏掉 95% 的货
  · 规则改了【不用重爬】,对库内数据重跑一遍即可全量重算
  · 错标(蹭流量挂错 designer)平台不管,只能自己清洗

watchlist.yaml 中每个品牌的 series 规则 + 全局 ITEM_TYPE_PATTERNS
共同产出三个标签:series / item_type / suspect_mislabel
"""

import re

# 品类判定(与 price_model.py 口径一致,按顺序首个命中生效)
ITEM_TYPE_PATTERNS = [
    ("jacket", r"jacket|bomber|varsity|blazer|ma-1|flight|coat|parka"),
    ("pants",  r"pants|jeans|denim(?!.*jacket)|trouser|cargo|bondage.*jean"),
    ("hoodie", r"hoodie|hoody|sweatshirt|pullover|zip.?up"),
    ("shirt",  r"(?<!t.)shirt|flannel|button|oxford"),
    ("tee",    r"\btee\b|t-shirt|tshirt|\bt shirt\b"),
    ("knit",   r"knit|sweater|cardigan|mohair"),
    ("shoes",  r"shoes|sneaker|boot|derby|loafer"),
]


# archive 卖家常只写季号不写品牌("AW03 Alpaca Cardigan"、"06SS Fuck It")。
# designer facet 已锁定品牌,标题再带季号即视为真货证据,避免误伤。
# 兼容字母在前(SS06 / A/W 03)与数字在前(06SS)两种写法。
SEASON_PATTERN = r"\b(ss|aw|fw|a/w|s/s|f/w)\s?'?\d{2}\b|\b\d{2}\s?(ss|aw|fw)\b"

# 仿款话术:出现即标记错标嫌疑("Hysteric Glamour STYLE fur" = 同款仿货)
KNOCKOFF_PATTERN = r"\b(inspired|bootleg|homage|repro|reproduction|replica)\b"


def classify_title(title: str, brand_cfg: dict) -> dict:
    """
    对单条标题打标签。
    返回 {"series": str|None, "item_type": str, "suspect_mislabel": 0/1}
    """
    t = (title or "").lower()

    # 1. 错标嫌疑:标题既不含品牌 token、也无季号行话 → 蹭流量错标嫌疑
    tokens = brand_cfg.get("title_tokens", [])
    has_token = any(tok.lower() in t for tok in tokens)
    has_season = re.search(SEASON_PATTERN, t) is not None
    suspect = 0 if (has_token or has_season) else 1

    # 仿款话术覆盖一切:"<品牌> style"、inspired、bootleg... 即使含品牌词也算嫌疑
    # 品牌词与 style 之间允许隔一个词("Hysteric Glamour Style"、"Helmut Lang style")
    if re.search(KNOCKOFF_PATTERN, t) or any(
        # tok 后允许残余字母(Hysterics 复数)、一个隔词(Glamour)、style 变体(styled/styling)
        re.search(rf"{re.escape(tok.lower())}\w*\s+(\w+\s+)?styl\w*", t) for tok in tokens
    ):
        suspect = 1

    # 2. 系列(watchlist 规则,首个命中)
    series = None
    for name, pattern in (brand_cfg.get("series") or {}).items():
        if re.search(pattern, t):
            series = name
            break

    # 3. 品类
    item_type = "other"
    for name, pattern in ITEM_TYPE_PATTERNS:
        if re.search(pattern, t):
            item_type = name
            break

    return {"series": series, "item_type": item_type, "suspect_mislabel": suspect}


def classify_rows(rows: list[dict], brand_cfg: dict) -> list[dict]:
    """对一批采集行就地打标签,返回同一列表方便链式调用。"""
    for r in rows:
        r.update(classify_title(r.get("title", ""), brand_cfg))
    return rows
