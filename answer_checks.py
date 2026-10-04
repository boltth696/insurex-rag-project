"""Focused checks for unsupported claims observed in the reviewed brochures.

These checks supplement evidence prompts and citations; they do not establish
the truth of every generated sentence or validate every possible paraphrase.
"""
import re


def unsupported_ci50_count(answer):
    """CI 50 is a rider name; the supplied Cheeva pages do not establish a count."""
    text = answer.replace('**','').replace('__','')
    if not re.search(r'\bci\s*50\b|cheeva|ชีวา|ซีไอ\s*50',text,re.I):
        return False
    patterns = [
        r'\b(?:covers?|covering|includes?|including|provides? (?:coverage|protection) (?:for|against)|(?:set|total|range) of)\s+(?:exactly |all |a total of )?(?:50|fifty)\s+(?:critical |specified |different |severe )*(?:illnesses|conditions|diseases)\b',
        r'(?:คุ้มครอง|ครอบคลุม)\s*(?:โรคร้ายแรง\s*)?50\s*(?:โรค|ชนิด)',
        r'โรคร้ายแรง\s*50\s*(?:โรค|ชนิด)',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern,text,re.I):
            # Allow a clear evidence limitation rather than treating its
            # quotation of a rejected claim as an affirmative count claim.
            prefix = re.split(r'[.!?;\n]',text[:match.start()])[-1][-140:]
            if re.search(r"(?:\bnot\s*$|\bcannot (?:assume|infer|confirm|verify)|\bcan['’]t (?:assume|infer|confirm|verify)|\bdoes not (?:establish|prove|confirm)|ไม่\s*$|ไม่(?:สามารถ)?(?:ยืนยัน|สรุป)|ยืนยันไม่ได้)",prefix,re.I):
                continue
            return True
    return False
