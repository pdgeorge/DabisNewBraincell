#!/usr/bin/env python3
"""
Google image search -> pick one -> force 500x500 -> overlay text at 1/3 height.

Usage (WSL/Ubuntu):
  python3 -m venv .venv && source .venv/bin/activate
  pip install requests pillow python-dotenv
  echo 'GOOGLE_API_KEY=your_api_key' > .env
  echo 'GOOGLE_CX=your_cx' >> .env

Run:
  python3 google_search.py "dude dancing on a horse" \
    --text "This is example text" \
    --font /path/to/ComicNeue-Bold.ttf \
    --out out.png
"""

import argparse
import io
import os
import random
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = lambda: None  # optional

GOOGLE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"


@dataclass
class ImageResult:
    url: str
    mime: Optional[str]


class InspoGenerator:
    """
    Class-based tool you can import and reuse.
    All knobs are instance attributes (self.*) with defaults you can override.
    """

    def __init__(
        self,
        query: str = "",
        api_key: Optional[str] = None,
        cx: Optional[str] = None,
        num: int = 10,
        size: int = 500,
        text: str = "This is example text",
        font: str = "./fonts/DejaVuSans-Bold.ttf",
        font_size: int = 40,
        out_path: str = "out.png",
        safe: str = "off",  # "off" | "active" | "high"
        timeout: int = 20,
        user_agent: str = "Mozilla/5.0 (Compat; DabiBraincell/1.0)",
        auto_fit: bool = True,  # shrink font if it overflows width
        stroke_width: int = 4,
        stroke_fill: Tuple[int, int, int, int] = (0, 0, 0, 220),
        text_fill: Tuple[int, int, int, int] = (255, 255, 255, 255),
    ):
        self.query = query
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.cx = cx or os.getenv("GOOGLE_CX")
        self.num = max(1, min(10, num))
        self.size = size
        self.text = text
        self.font = font
        self.font_size = font_size
        self.out_path = out_path
        self.safe = safe
        self.timeout = timeout
        self.user_agent = user_agent
        self.auto_fit = auto_fit
        self.stroke_width = stroke_width
        self.stroke_fill = stroke_fill
        self.text_fill = text_fill

    # --------------------------- Public API ---------------------------

    def run(self) -> str:
        """End-to-end: search -> download -> choose -> process -> save. Returns output path."""
        self._require_creds()
        results = self.search_images(self.query)
        imgs = self.download_top_images(results)
        if not imgs:
            raise RuntimeError("Failed to download any of the top results.")
        chosen = random.choice(imgs)
        final = self.process_image(chosen)
        self.overlay_text(final)
        final.save(self.out_path, "PNG")
        return self.out_path

    def search_images(self, query: str) -> List[ImageResult]:
        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": query,
            "searchType": "image",  # official image search mode
            "num": self.num,
            "safe": self.safe,
        }
        r = requests.get(GOOGLE_ENDPOINT, params=params, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        out: List[ImageResult] = []
        for it in (data.get("items") or []):
            link = it.get("link")
            if link:
                out.append(ImageResult(url=link, mime=it.get("mime")))
        return out

    def download_top_images(self, results: List[ImageResult]) -> List[Image.Image]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "image/*,*/*;q=0.8",
        }
        images: List[Image.Image] = []
        for r in results:
            try:
                resp = requests.get(r.url, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                bio = io.BytesIO(resp.content)
                img = Image.open(bio)
                img.load()
                images.append(img)
            except Exception:
                continue
        return images

    def process_image(self, img: Image.Image) -> Image.Image:
        """Force 500x500 (or self.size) with NO aspect preservation."""
        return img.convert("RGBA").resize((self.size, self.size), Image.LANCZOS)

    def overlay_text(self, img: Image.Image) -> None:
        """Center a wrapped text block horizontally, and center that block around the 1/3 height line."""
        draw = ImageDraw.Draw(img)

        # Load a scalable font (TTF/OTF). If you haven't set self.font, make sure _load_font tries a system TTF.
        font = self._load_font(self.font, self.font_size)

        # Wrap to ~90% of canvas width
        max_width_px = int(img.width * 0.9)
        lines = self._wrap_text_words(draw, self.text, font, max_width_px=max_width_px)

        # Compute total block height (line spacing ~20% of font size)
        line_spacing = max(2, int(getattr(font, "size", 20) * 0.2))
        line_metrics = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font, stroke_width=self.stroke_width)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            line_metrics.append((line, w, h))

        total_h = sum(h for _, _, h in line_metrics) + line_spacing * (max(len(line_metrics) - 1, 0))

        # Start so the whole block is centered around 2/3 height
        start_y = img.height * (6.0 / 7.0) - total_h / 2.0

        # Draw each line centered horizontally
        y = start_y
        for line, w, h in line_metrics:
            x = (img.width - w) / 2.0
            draw.text(
                (x, y),
                line,
                font=font,
                fill=self.text_fill,
                stroke_width=self.stroke_width,
                stroke_fill=self.stroke_fill,
            )
            y += h + line_spacing


    # --------------------------- Internals ---------------------------

    def _require_creds(self) -> None:
        if not self.api_key or not self.cx:
            raise RuntimeError("Missing GOOGLE_API_KEY / GOOGLE_CX (env or parameters).")

    def _load_font(self, font_path: Optional[str], size: int) -> ImageFont.FreeTypeFont:
        try:
            if font_path:
                return ImageFont.truetype(font_path, size=size)
        except Exception:
            pass

        return ImageFont.load_default()


    def _fit_font_to_width(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont,
        target_px: int,
        min_size: int = 16,
    ) -> ImageFont.FreeTypeFont:
        """Shrink font until text width <= target_px (keeps current size if already fits)."""
        try:
            # If the font is default bitmap, bail (no size control)
            if not hasattr(font, "size"):
                return font
            size = getattr(font, "size", self.font_size)
            current = font
            while size >= min_size:
                bbox = draw.textbbox((0, 0), text, font=current, stroke_width=self.stroke_width)
                width = bbox[2] - bbox[0]
                if width <= target_px:
                    return current
                size = max(min_size, int(size * 0.9))
                current = ImageFont.truetype(self.font, size=size) if self.font else ImageFont.load_default()
            return current
        except Exception:
            return font

    def _wrap_text_words(self, draw, text, font, max_width_px: int) -> list[str]:
        """
        Word-wrap 'text' to lines that fit within max_width_px, using whole words.
        No hyphenation; if a single word exceeds max_width_px, it becomes its own line (may overflow).
        """
        lines = []
        for paragraph in text.splitlines() or [""]:
            words = paragraph.split(" ")
            if not words:
                lines.append("")
                continue

            current = words[0]
            for word in words[1:]:
                candidate = current + " " + word
                # Measure with stroke taken into account (more accurate than char counts)
                bbox = draw.textbbox((0, 0), candidate, font=font, stroke_width=self.stroke_width)
                cand_w = bbox[2] - bbox[0]
                if cand_w <= max_width_px:
                    current = candidate
                else:
                    # push current line, start a new one with this word
                    lines.append(current)
                    current = word

            # last line in paragraph
            lines.append(current)
        return lines


# --------------------------- CLI ---------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Google image search -> force 500x500 -> overlay text at 1/3 height.")
    p.add_argument("query", help="Search query, e.g., 'dude dancing on a horse'")
    p.add_argument("--num", type=int, default=10)
    p.add_argument("--size", type=int, default=500)
    p.add_argument("--text", default="This is example text")
    p.add_argument("--font", default=None, help="Path to a .ttf/.otf (e.g., ComicNeue-Bold.ttf)")
    p.add_argument("--font-size", type=int, default=20, help="Default is big and readable")
    p.add_argument("--out", dest="out_path", default="out.png")
    p.add_argument("--safe", default="off", choices=["off", "active", "high"])
    p.add_argument("--no-auto-fit", action="store_true", help="Disable auto-shrinking if text is too wide")
    return p.parse_args()


def main():
    load_dotenv()
    args = parse_args()

    maker = InspoGenerator(
        query=args.query,
        num=args.num,
        size=args.size,
        text=args.text,
        font_size=args.font_size,
        out_path=args.out_path,
        safe=args.safe,
        auto_fit=not args.no_auto_fit,
    )
    print(f"{maker.text=}")
    print(f"{maker.font=}")
    print(f"{maker.font_size=}")
    out = maker.run()

    print(f"Saved {out}")

if __name__ == "__main__":
    main()
