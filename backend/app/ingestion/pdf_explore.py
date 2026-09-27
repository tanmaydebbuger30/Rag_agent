HHS_PATH = "data/raw/regulatory/techsafeguards.pdf"
import pymupdf


def classify_line(size, font, text):
    if size == 12 and "Bold" in font and "§ 164.312" in text:
        return "SPEC"


    elif any(character.isalpha() for character in text):
        if size == 16 and "Bold" in font:
            return "SECTION"

    else:
        return None
        

def main():
    doc = pymupdf.open(HHS_PATH)
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = line["spans"]
                text = "".join(s["text"] for s in spans).strip()
                if not text:
                    continue
                first = spans[0]
                kind = classify_line(round(first["size"]), first["font"], text)
                if kind:
                    print(f"p{page.number + 1:<3} {kind:<10} {text}")


if __name__ == "__main__":
    main()