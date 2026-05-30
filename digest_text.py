"""Text cleaning helpers for digest generation."""
import re
from html import unescape

from digest_config import BAD_LLM_MARKERS


def strip_html(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"<li[^>]*>", "\n- ", text, flags=re.I)
    text = re.sub(r"</(p|h\d|ul|ol|li)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def release_bullets(content: str) -> list[str]:
    bullets = []
    for match in re.finditer(r"<li[^>]*>(.*?)</li>", content or "", flags=re.I | re.S):
        bullet = strip_html(match.group(1))
        if bullet:
            bullets.append(bullet)
    if bullets:
        return bullets
    return [
        line.strip("- ").strip()
        for line in strip_html(content).splitlines()
        if line.strip().startswith("- ")
    ]


def one_line(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", strip_html(text)).strip()
    text = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip("，。；：、,. ") + "。"


def clean_llm_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip().replace("**", "")
    text = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", text)
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"（?\d+\s*个中文字符）?", "", text)
    text = re.sub(r"^\s*[\"“”']+", "", text).strip()
    return text


def bad_llm_text(text: str) -> bool:
    return any(marker in text for marker in BAD_LLM_MARKERS)


def sanitize_product_text(text: str) -> str:
    text = clean_llm_text(text)
    text = text.replace("---", " ")
    text = re.sub(r"^根据你的要求[，,：:].*?(?:中文摘要|摘要)[：:]\s*", "", text)
    text = re.sub(r"^根据这条信息[，,，]*为您准备以下摘要[：:]\s*", "", text)
    text = re.sub(r"^根据这条信息[，,，]*", "", text)
    text = re.sub(r"^#\s*\d{4}年\d{1,2}月\d{1,2}日信息摘要\s*", "", text)
    text = re.sub(r"字数统计[：:].*$", "", text)
    text = re.sub(r"摘要直接陈述.*$", "", text)
    text = re.sub(r"Codex（应该[^）]+）", "Codex", text)
    text = re.sub(r"Claude Code（应该[^）]+）", "Claude Code", text)
    text = text.replace("这条更新值得看，因为", "")
    text = text.replace("你可以把它当成今天的行动线索：", "")
    text = text.replace("这条更新很短，核心信息是：", "")
    text = text.replace("它本身不是完整新闻，但可以作为今天的信号来源，用来判断相关产品、工具或市场采用是否正在升温。", "")
    text = re.sub(r"对这个产品产品线的影响[：:].*?(?=。|$)", "", text)
    text = re.sub(r"对我们(?:来说)?[，,：:].*?(?=。|$)", "", text)
    text = re.sub(r"可作为Line\s*\d+[^。]*", "", text)
    text = re.sub(r"(?:产品线|内容线|交易线)[^。]*(?:。|$)", "", text)
    text = re.sub(r"\s+", " ", text).strip(" 。")
    if text:
        text += "。"
    return text


def consumer_text(text: str) -> str:
    text = sanitize_product_text(text)
    text = re.sub(r"^[^。！？：:\n]{1,40}围绕这一主题更新[：:]\s*", "", text)
    text = re.sub(r"^[^。！？：:\n]{1,40}提到[：:]\s*", "", text)
    text = re.sub(r"这对\s*Park-IO\s*的?", "这对", text)
    text = text.replace("Park-IO", "这个产品")
    text = text.replace("这会影响今天对工具工作流、内容选题或后续跟进来源的判断。", "")
    text = text.replace("这补充了官方发布之外的实际使用场景、产品体验变化和社区反馈，可作为应用层案例记录。", "")
    text = re.sub(r"\s+", " ", text).strip(" 。")
    return f"{text}。" if text else ""
