"""Quoted customer facts must not match a fragment of a larger number."""
import re
from .comparison import quote_key


def contains_customer_quote(quote, text):
    needle, haystack = quote_key(quote), quote_key(str(text))
    if not needle:
        return False
    start = 0
    while True:
        index = haystack.find(needle, start)
        if index < 0:
            return False
        end = index + len(needle)
        before_ok = not needle[0].isdigit() or index == 0 or not haystack[index - 1].isdigit()
        after_ok = not needle[-1].isdigit() or end == len(haystack) or not haystack[end].isdigit()
        # Decimal points and thousands commas join parts of one number.
        # Ordinary sentence punctuation or a list such as 'ages 20,21' does
        # not. Do not let a budget of 20,000 supply an invented age of 20.
        if needle[0].isdigit() and index >= 2 and haystack[index - 2].isdigit():
            separator = haystack[index - 1]
            if separator == "." or separator == "," and re.match(r"\d{3}(?:\D|$)", haystack[index:]):
                before_ok = False
        if needle[-1].isdigit():
            suffix = haystack[end:]
            if re.match(r"\.\d|,\d{3}(?:\D|$)", suffix):
                after_ok = False
        if before_ok and after_ok:
            return True
        start = index + 1


def customer_quote_position(quote, humans):
    return max((i for i, message in enumerate(humans) if contains_customer_quote(quote, message.content)), default=-1)


def explicit_customer_change(quote, latest):
    """Resetting a person requires a transition, not a name introduction."""
    if not contains_customer_quote(quote, latest):
        return False
    if re.search(r"(?:not|isn['’]t|is not|don['’]t|do not)\s+(?:a\s+|the\s+)?(?:new|different|another|next)\s+(?:customer|client|person|profile)|same\s+(?:customer|client|person)|ไม่ใช่ลูกค้า(?:ใหม่|คนใหม่|คนอื่น)|ลูกค้าคนเดิม", latest, re.I):
        return False
    return bool(re.search(
        r"\b(?:different|another|new|next)\s+(?:(?:potential|insurance)\s+)?(?:customer|client|person|prospect|case|group|profile)\b"
        r"|\b(?:switch|change|move)(?:ing)?\b.{0,40}\b(?:customer|client|person|prospect)\b"
        r"|\bnow\b.{0,20}\b(?:my|for)\b.{0,20}\b(?:wife|husband|mother|father|sister|brother)\b"
        r"|ลูกค้า(?:คนใหม่|ใหม่|คนอื่น|อีกคน)|คนละคน|เปลี่ยน.{0,15}ลูกค้า", quote, re.I))


def explicit_lead_cancellation(quote, latest):
    if not contains_customer_quote(quote, latest):
        return False
    if re.search(r"(?:don['’]t|do not|must not|should not)\s+(?:please\s+)?(?:cancel|stop)|not\s+cancell?ing|อย่า(?:ยกเลิก|หยุด)", latest, re.I) and not re.search(r"(?:but|instead|actually)\s+(?:please\s+)?(?:cancel|stop)|แต่.{0,8}(?:ยกเลิก|หยุด)", latest, re.I):
        return False
    if re.match(r"\s*(?:what|how|when|why|would|does|can i|if|suppose)\b", latest, re.I) and not re.search(r"(?:^|[.!]\s*)(?:please\s+)?(?:cancel|stop)\s+(?:this|collection|the lead|my request)", latest, re.I):
        return False
    return bool(re.search(
        r"\bcancel\b|\bstop\b|\bnever\s*mind\b|\bforget (?:it|this)\b|not interested"
        r"|(?:don['’]t|do not|won['’]t|will not|rather not|refuse to).{0,35}(?:share|provide|give|continue|contact|buy|apply)"
        r"|ยกเลิก|ไม่สนใจ|ไม่(?:ต้องการ|อยาก|สะดวก).{0,20}(?:ให้|บอก|แชร์|กรอก|ติดต่อ|สมัคร|ซื้อ)", quote, re.I))
