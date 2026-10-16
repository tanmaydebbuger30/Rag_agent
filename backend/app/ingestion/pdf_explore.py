import pymupdf

HHS_PATH = "data/raw/regulatory/techsafeguards.pdf"


def classify_line(size, font, text):
    # A specification heading: 12pt bold, mentions the regulation section
    if size == 12 and "Bold" in font and "§ 164.312" in text:
        return "SPEC"

    # A section heading: 16pt bold, with at least one letter (skips bold numbers)
    if size == 16 and "Bold" in font and any(ch.isalpha() for ch in text):
        return "SECTION"

    # Everything else is body text
    return None

def build_sections(doc):
    sections = []          # finished sections
    current = None         # the section being filled right now
    prev_bold12 = None     # NEW: last body line, if it was 12pt bold (a possible heading start)

    for page in doc:
        page_num = page.number + 1

        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = line["spans"]
                text = "".join(s["text"] for s in spans).strip()
                if not text:
                    continue

                first = spans[0]
                size = round(first["size"])

                if size >= 28:
                    continue

                kind = classify_line(size, first["font"], text)

                if kind:
                    # NEW: a SPEC heading wrapped onto two lines.
                    # If the line right before it was 12pt bold body text, it's the
                    # first half of this heading: move it from the old section to here.
                    if (kind == "SPEC" and prev_bold12 is not None and current is not None
                            and current["lines"] and current["lines"][-1] == prev_bold12):
                        current["lines"].pop()
                        text = f"{prev_bold12} {text}"

                    if current is not None:
                        sections.append(current)

                    current = {
                        "heading": " ".join(text.split()),   # NEW: collapse double spaces
                        "kind": kind,
                        "page_start": page_num,
                        "page_end": page_num,
                        "lines": [],
                    }
                    prev_bold12 = None

                elif current is not None:
                    current["lines"].append(text)
                    current["page_end"] = page_num
                    # NEW: remember this line only if it's 12pt bold
                    prev_bold12 = text if (size == 12 and "Bold" in first["font"]) else None

    if current is not None:
        sections.append(current)

    return sections


def main():
    doc = pymupdf.open(HHS_PATH)
    sections = build_sections(doc)

    print(f"Found {len(sections)} sections\n")

    for s in sections:
        text = "\n".join(s["lines"])
        pages = f"p.{s['page_start']}-{s['page_end']}"
        print(f"{s['kind']:<8} {pages:<8} {len(text):>6} chars   {s['heading']}")


if __name__ == "__main__":
    main()