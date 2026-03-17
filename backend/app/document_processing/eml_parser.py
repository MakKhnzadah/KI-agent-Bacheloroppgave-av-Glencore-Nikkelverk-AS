from __future__ import annotations

import re
from email import policy
from email.parser import BytesParser


def eml_parser(content: bytes) -> str:
    msg = BytesParser(policy=policy.default).parsebytes(content)

    parts: list[str] = []
    subject = msg.get("subject")
    if subject:
        parts.append(f"Subject: {subject}")

    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            if ctype == "text/plain":
                try:
                    parts.append(part.get_content())
                except Exception:
                    continue
    else:
        ctype = (msg.get_content_type() or "").lower()
        if ctype == "text/plain":
            try:
                parts.append(msg.get_content())
            except Exception:
                pass

    text = "\n\n".join(p for p in parts if p and p.strip())
    return re.sub(r"\s+", " ", text).strip()
