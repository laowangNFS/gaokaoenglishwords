#!/usr/bin/env python3
"""生成 ClassIsland「高考必背3600词」插件的本地 XML 词库。

数据来源：
  * 高考英语 3500 词表：https://github.com/pluto0x0/word3500（MIT）
    实际读取 qwerty-learner 中已切分好的 GaoKao_3500.json（GPL-3.0），
    仅使用其词条切分、音标与整理释义；词性和缺失释义由 ECDICT 校正。
  * ECDICT：https://github.com/skywind3000/ECDICT（MIT）

用法：
    python tools/build_vocab.py                 # 收录全部 3810 条
    python tools/build_vocab.py --target 3600   # 按词频截取 3600 条
    python tools/build_vocab.py --check         # 只校验现有 XML

脚本首次运行会把两个源文件下载到 tools/.cache/（约 70 MB），之后复用缓存。
日常构建不需要运行本脚本，仓库中已提供生成好的 Assets/gaokao3600.xml。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "tools" / ".cache"
OUT = ROOT / "Assets" / "gaokao3600.xml"

QWERTY_URL = (
    "https://raw.githubusercontent.com/RealKai42/qwerty-learner/"
    "master/public/dicts/GaoKao_3500.json"
)
ECDICT_URL = "https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv"

QWERTY_FILE = CACHE / "GaoKao_3500.json"
ECDICT_FILE = CACHE / "ecdict.csv"

# qwerty 中把多个词形写在一个 name 里的情况。
VARIANT_HEADS = {
    "ambassador ambassadress": "ambassador",
    "can could": "can",
    "could modal": "could",
    "does doesn't": "does",
    "does doesnˈt": "does",
    "hold held held": "hold",
    "may modal": "may",
    "must modal": "must",
    "teach taught taught": "teach",
    "wake woke woken": "wake",
    "turning n": "turning",
}

# 常见词的释义修正：源数据里存在跨词条串行、单复数串行等问题。
MEANING_FIXES = {
    "a": "一（个、件……）",
    "ad": "广告",
    "after": "在…之后；后来",
    "an": "一（个、件……）",
    "can": "能，可以；（美）罐头，罐子",
    "do": "做，干；用于构成疑问句和否定句",
    "female": "女性的；雌性的",
    "look": "看，瞧；看起来",
    "no": "不，不是；没有，无",
    "one": "一（个、只……）",
    "skipping": "跳绳",
    "the": "这（那）个，这（那）些",
    "very": "很，非常",
    "war": "战争",
}

# 源数据行错位导致丢失的常用词。
MANUAL_ENTRIES = {
    "body": ("n.", "身体；主体", "ˈbɒdi"),
    "policewoman": ("n.", "女警察", "pəˈliːswʊmən"),
    "warn": ("vt.", "警告，提醒", "wɔːn"),
}

POS_FIXES = {
    "can": ["v. / n."],
    "do": ["v. / aux."],
    "one": ["pron. / num."],
    "p.c.": ["n."],
    "pencil-sharpener": ["n."],
    "show": ["n. / v."],
    "skipping": ["n."],
    "very": ["adv."],
    "war": ["n."],
    "x-ray": ["n."],
    "zebra-crossing": ["n."],
}

# 源数据大小写错误：这些是普通名词，不应显示为首字母大写。
CASE_FIXES = {
    "baby": "baby",
    "dynamic": "dynamic",
    "dynasty": "dynasty",
    "indicate": "indicate",
    "mom": "mom",
    "mosquito": "mosquito",
    "scratch": "scratch",
}

POS_ALIASES = {
    "a": "adj.",
    "ad": "adv.",
    "adj": "adj.",
    "adv": "adv.",
    "n": "n.",
    "v": "v.",
    "vt": "vt.",
    "vi": "vi.",
    "prep": "prep.",
    "pron": "pron.",
    "conj": "conj.",
    "num": "num.",
    "art": "art.",
    "int": "int.",
    "interj": "int.",
    "aux": "aux.",
    "abbr": "abbr.",
    "pl": "pl.",
    "t": "vt.",
    "vn": "v. / n.",
    "vnum": "num.",
    "vad": "adv.",
    "modal v": "modal v.",
    "modal": "modal v.",
    "mod": "modal v.",
    "r": "adv.",
}

POS_RE = re.compile(
    r"(?<![A-Za-z])(modal\s+v|interj|vnum|vn|vad|adj|adv|abbr|aux|conj|num|prep|pron|"
    r"art|int|pl|vt|vi|n|v|a|ad|t|mod)(?:\.|\u3002|(?=\s*[（(]))",
    re.IGNORECASE,
)
POS_NODOT_RE = re.compile(
    r"^\s*(n|vt|vi|v|adj|adv|a|ad|prep|pron|conj|num|art|int|interj|aux)\s+",
    re.IGNORECASE,
)
FORM_NOTE_RE = re.compile(r"【[^】]*】")
PUA_RE = re.compile(r"[\ue000-\uf8ff]")
LEADING_EN_FORM_RE = re.compile(r"^\s*[（(]\s*[A-Za-z][A-Za-z ,.'’\-]*[）)]\s*")
PAREN_RE = re.compile(r"[（(][^）)]*[）)]")

FORM_NOTE_KEYWORDS = ("过去式", "过去分词", "比较级", "最高级", "单数", "复数", "第三人称")


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Englishwordsshow/1.0"})
    for attempt in range(1, 4):
        try:
            print(f"下载 {url} ...")
            with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as f:
                while chunk := response.read(1024 * 256):
                    f.write(chunk)
            print(f"已保存 {target} ({target.stat().st_size / 1024 / 1024:.1f} MiB)")
            return
        except Exception as ex:  # noqa: BLE001 - 网络错误统一重试
            print(f"  第 {attempt} 次下载失败: {ex}")
            time.sleep(2 * attempt)
    raise SystemExit(f"无法下载 {url}，请手动放到 {target}")


def ensure_sources() -> None:
    if not QWERTY_FILE.exists():
        download(QWERTY_URL, QWERTY_FILE)
    if not ECDICT_FILE.exists():
        download(ECDICT_URL, ECDICT_FILE)


def normalize_headword(raw: str, form_note: bool = False) -> str | None:
    """返回可独立展示的单字词条；短语、带括号变形等返回 None。"""
    original = unicodedata.normalize("NFC", raw.strip())
    w = original.replace("（", "(").replace("）", ")")
    w = re.sub(r"\s*\(.*$", "", w).strip()
    w = w.split("=")[0].strip()
    if "/" in w:
        w = w.split("/")[0].strip()
    if " " in w:
        key = re.sub(r"\s+", " ", w.lower())
        if key in VARIANT_HEADS:
            w = VARIANT_HEADS[key]
        elif form_note:
            w = w.split()[0]
        else:
            return None
    if re.fullmatch(r"[a-z]+\.", w):
        w = w[:-1]
    if not re.fullmatch(r"[A-Za-z][A-Za-z'.\-]*", w):
        return None
    return w


def extract_pos(text: str) -> list[str]:
    pos: list[str] = []
    for match in POS_RE.finditer(text):
        token = re.sub(r"\s+", " ", match.group(1).lower())
        norm = POS_ALIASES.get(token)
        if norm:
            for part in norm.split(" / "):
                if part not in pos:
                    pos.append(part)
    return pos


def clean_leftovers(text: str) -> str:
    """清理行错位后残留的单个字母碎片。"""
    text = re.sub(r"^\s*[a-z]\s+(?=[\u4e00-\u9fff(])", "", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff)])\s+[a-z]\s+(?=[\u4e00-\u9fff(])", "；", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff)])\s+(?=[\u4e00-\u9fff(])", "；", text)
    return text.strip()


def tidy_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = FORM_NOTE_RE.sub("", text)
    text = PUA_RE.sub("", text)
    text = text.replace("（", "(").replace("）", ")")
    text = LEADING_EN_FORM_RE.sub("", text)
    text = re.sub(r"^\s*[（(]\s*(缩|复|pl\.)[^）)]*[）)]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*[*＊]\s*", "", text)
    text = re.sub(r"^\s*[a-z]\s+(?=[\u4e00-\u9fff(])", "", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff)])\s+[a-z]\s+(?=[\u4e00-\u9fff(])", "；", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff)])\.(?=[\u4e00-\u9fff(])", "；", text)
    text = re.sub(r"\[[^\]]{1,8}\]", "", text)
    text = text.replace("&", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff)])\s+(?=[\u4e00-\u9fff(])", "；", text)
    return text.strip(" ;；,，.。/、-—")


def strip_pos(text: str) -> str:
    text = POS_RE.sub("", text)
    match = POS_NODOT_RE.match(text)
    if match:
        text = text[match.end():]
    return text


def clean_meaning(
    text: str,
    head: str,
    headwords: set[str],
    already_tidy: bool = False,
) -> tuple[str, list[str]]:
    if not already_tidy:
        text = tidy_text(text)
    pos = extract_pos(text)
    text = strip_pos(text)
    text = clean_leftovers(text)

    # 跨词条串行检测：括号外出现另一个词库词条，例如“泛舟 body 身体”。
    masked = PAREN_RE.sub(lambda match: " " * len(match.group(0)), text)
    cut = len(masked)
    for match in re.finditer(r"(?<![A-Za-z])[A-Za-z][A-Za-z'\-]{2,}(?![A-Za-z])", masked):
        token = match.group(0).lower()
        if token == head.lower() or token in headwords:
            cut = min(cut, match.start())
            break
    if cut < len(masked):
        text = clean_leftovers(tidy_text(text[:cut]))

    text = re.sub(r"=\s*[A-Za-z][A-Za-z .'\-]*", "", text)
    text = text.strip(" ;；,，.。/、-—")

    parts: list[str] = []
    for part in re.split(r"[;；]", text):
        part = part.replace(",", "，").strip(" ，,、/")
        if not part or not re.search(r"[\u4e00-\u9fff]", part):
            continue
        if part not in parts:
            if "，" not in part and any(
                part == sense for existing in parts for sense in existing.split("，")
            ):
                continue
            parts.append(part)
    return "；".join(parts), pos


def clean_qwerty_gloss(text: str, head: str, headwords: set[str]) -> str:
    text = tidy_text(text)
    text = strip_pos(text)
    zh, _ = clean_meaning(text, head, headwords, already_tidy=True)
    return zh


def ecdict_gloss(row: dict | None) -> tuple[str, list[str]]:
    if not row:
        return "", []
    text = row.get("translation", "").replace("\\r\\n", "\n").replace("\\n", "\n")
    pos: list[str] = []
    glosses: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("["):
            continue
        line = re.sub(r"\[[^\]]{1,8}\]", "", line).strip()
        line_pos = extract_pos(line)
        body = strip_pos(line)
        body = body.replace(",", "，").replace(";", "；").strip(" 。，；")
        senses = [sense.strip() for sense in re.split(r"[，；]", body) if sense.strip()]
        senses = senses[:3]
        if not senses:
            continue
        for item in line_pos:
            if item not in pos:
                pos.append(item)
        if len(glosses) >= 2:
            continue
        glosses.append("，".join(senses))
    return "；".join(glosses), pos


def load_ecdict(words: set[str]) -> dict[str, dict]:
    wanted = {word.lower() for word in words}
    rows: dict[str, dict] = {}
    with ECDICT_FILE.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = row["word"].strip().lower()
            if key in wanted and key not in rows:
                rows[key] = row
    return rows


def frequency_key(row: dict | None) -> float:
    if not row:
        return 1e12
    values = []
    for field in ("frq", "bnc"):
        try:
            value = int(row.get(field) or 0)
        except ValueError:
            value = 0
        if value > 0:
            values.append(value)
    return float(min(values)) if values else 1e12


def xml_attr(value: str) -> str:
    value = value.replace("&", "&amp;").replace('"', "&quot;")
    return value.replace("<", "&lt;").replace(">", "&gt;")


def build(target: int) -> int:
    ensure_sources()

    source = json.loads(QWERTY_FILE.read_text(encoding="utf-8"))
    merged: "OrderedDict[str, dict]" = OrderedDict()
    skipped = 0

    for item in source:
        trans = item.get("trans") or []
        trans_text = " ".join(str(t) for t in trans)
        form_note = any(word in trans_text for word in FORM_NOTE_KEYWORDS)
        head = normalize_headword(str(item.get("name", "")), form_note)
        if not head:
            skipped += 1
            continue

        key = head.lower()
        head = CASE_FIXES.get(key, head)
        entry = merged.setdefault(
            key,
            {
                "word": head,
                "raw_glosses": [],
                "pos": [],
                "phonetic": item.get("ukphone") or item.get("usphone") or "",
                "freq": 1e12,
            },
        )
        if len(head) > len(entry["word"]):
            entry["word"] = head

        for one in trans:
            entry["raw_glosses"].append(str(one))
            for pos in extract_pos(str(one)):
                if pos not in entry["pos"]:
                    entry["pos"].append(pos)

    for key, (pos, zh, phonetic) in MANUAL_ENTRIES.items():
        if key in merged:
            continue
        merged[key] = {
            "word": key,
            "raw_glosses": [],
            "pos": [pos],
            "phonetic": phonetic,
            "freq": 1e12,
            "manual_zh": zh,
        }

    heads = {entry["word"].lower() for entry in merged.values()}
    headwords = {head for head in heads if len(head) >= 3}
    ecdict = load_ecdict(set(heads))

    fallback_used: list[str] = []
    residual: list[tuple[str, str]] = []
    for key, entry in merged.items():
        row = ecdict.get(key)
        entry["freq"] = frequency_key(row)

        glosses: list[str] = []
        for raw in entry["raw_glosses"]:
            zh = clean_qwerty_gloss(raw, entry["word"], headwords)
            if zh and zh not in glosses:
                glosses.append(zh)
        text = "；".join(glosses)

        ecdict_text, ecdict_pos = ecdict_gloss(row)
        if entry.get("manual_zh"):
            text = entry["manual_zh"]
        if key in MEANING_FIXES:
            text = MEANING_FIXES[key]
        if not text:
            text = ecdict_text
            fallback_used.append(entry["word"])
        elif ecdict_text and re.search(
            r"(?<![A-Za-z])(body|hang|policewoman|show|link)(?![A-Za-z])", text
        ):
            residual.append((entry["word"], text))

        if key in POS_FIXES:
            entry["pos"] = POS_FIXES[key]
        elif ecdict_pos:
            entry["pos"] = ecdict_pos
        elif not entry["pos"]:
            entry["pos"] = ["n."]

        entry["zh"] = text or ecdict_text or entry["word"]

    items = list(merged.values())
    dropped: list[dict] = []
    if target > 0 and len(items) > target:
        items.sort(key=lambda entry: (entry["freq"], entry["word"].lower()))
        dropped = items[target:]
        items = items[:target]

    # 用去掉标点后的键排序，避免 "a.m." 排在 "abandon" 前面。
    items.sort(key=lambda entry: (re.sub(r"[^a-z0-9]", "", entry["word"].lower()), entry["word"].lower()))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write(
            '<wordbook name="高考必背3600词" count="%d" '
            'source="word3500 / ECDICT" version="1.0">\n' % len(items)
        )
        for entry in items:
            f.write(
                '  <word en="%s" pos="%s" zh="%s" phonetic="%s" />\n'
                % (
                    xml_attr(entry["word"]),
                    xml_attr(" / ".join(entry["pos"]) or "n."),
                    xml_attr(entry["zh"]),
                    xml_attr(entry["phonetic"]),
                )
            )
        f.write("</wordbook>\n")

    print(f"词条：{len(items)}（跳过短语/变形 {skipped} 条）")
    print(f"ECDICT 回退释义：{len(fallback_used)} {fallback_used[:10]}")
    print(f"残留串行：{len(residual)} {residual[:5]}")
    if dropped:
        print(f"按词频舍弃：{len(dropped)} 条，例如：{[entry['word'] for entry in dropped[:15]]}")
    print(f"已写入 {OUT}（{OUT.stat().st_size / 1024:.1f} KiB）")
    return 0


def check() -> int:
    if not OUT.exists():
        print(f"文件不存在：{OUT}")
        return 1

    root = ET.parse(OUT).getroot()
    words = root.findall("word")
    errors: list[str] = []
    seen: set[str] = set()

    for word in words:
        en = (word.get("en") or "").strip()
        pos = (word.get("pos") or "").strip()
        zh = (word.get("zh") or "").strip()
        if not en or not zh:
            errors.append(f"空字段：{en!r}")
        if not pos:
            errors.append(f"缺词性：{en}")
        if en.lower() in seen:
            errors.append(f"重复词条：{en}")
        seen.add(en.lower())
        if not re.search(r"[\u4e00-\u9fff]", zh):
            errors.append(f"释义没有中文：{en} -> {zh}")

    print(f"词条数：{len(words)}")
    print(f"声明数量：{root.get('count')}")
    print(f"唯一英文：{len(seen)}")
    if errors:
        print(f"发现 {len(errors)} 个问题：")
        for error in errors[:50]:
            print(f"  {error}")
        return 1
    print("校验通过：字段完整、无重复、释义含中文。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="生成/校验高考必背3600词 XML")
    parser.add_argument("--target", type=int, default=0, help="只保留前 N 条（按词频），默认全部")
    parser.add_argument("--check", action="store_true", help="只校验现有 XML，不重新生成")
    args = parser.parse_args()

    if args.check:
        return check()
    if args.target < 0:
        parser.error("--target 不能为负数")
    result = build(args.target)
    if result == 0:
        result = check()
    return result


if __name__ == "__main__":
    sys.exit(main())

