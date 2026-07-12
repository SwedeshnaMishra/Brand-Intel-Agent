from __future__ import annotations
import os

from schemas import BrandIntelligence
from utils.logger import log


def write_markdown(data: BrandIntelligence, output_dir: str) -> str:
    path = os.path.join(output_dir, f"{data.brand_name}.md")
    try:
        lines: list[str] = []
        lines.append(f"# Brand Intelligence Report: {data.brand_name}")
        lines.append("")

        lines.append("## Brand Overview")
        lines.append(f"- **Portals live:** {', '.join(data.portals_live) if data.discovery.found_on_amazon else 'None found'}")
        lines.append(f"- **Category:** {data.discovery.category or 'Unknown'}")
        lines.append(f"- **Sub-Category:** {data.discovery.sub_category or 'Unknown'}")
        lines.append(f"- **Found on Amazon.in:** {'Yes' if data.discovery.found_on_amazon else 'No'}")
        lines.append("")

        lines.append("## Product Catalog")
        if data.marketplace.products:
            for p in data.marketplace.products:
                lines.append(f"- [{p.title or p.url}]({p.url})")
        else:
            lines.append("_No products discovered._")
        lines.append("")

        lines.append("## Marketplace Intelligence")
        lines.append("| Product | Rating Count | Star Rating | Seller | Sponsored |")
        lines.append("|---|---|---|---|---|")
        for p in data.marketplace.products:
            short_title = (p.title[:40] + "...") if len(p.title) > 40 else (p.title or p.url)
            lines.append(
                f"| {short_title} | {p.rating_count} | {p.star_rating} | "
                f"{p.seller_name or 'Unknown'} | {'Yes' if p.is_sponsored else 'No'} |"
            )
        lines.append("")
        lines.append(f"- **Unique sellers:** {', '.join(data.marketplace.sellers) or 'None'}")
        lines.append(f"- **Running sponsored ads:** {'Yes' if data.marketplace.running_ads else 'No'}")
        lines.append("")

        lines.append("## Listing Quality Audit")
        lines.append(f"**Score: {data.listing_quality.score} / 10**")
        lines.append("")
        if data.listing_quality.summary:
            lines.append(f"_{data.listing_quality.summary}_")
            lines.append("")
        if data.listing_quality.dimensions:
            lines.append("| Dimension | Verdict | Notes |")
            lines.append("|---|---|---|")
            for d in data.listing_quality.dimensions:
                lines.append(f"| {d.dimension} | {d.verdict.value} | {d.notes} |")
        else:
            lines.append("_No listing quality data available._")
        lines.append("")

        lines.append("## Weakness Report")
        if data.weakness.bullets:
            for b in data.weakness.bullets:
                lines.append(f"- {b}")
        else:
            lines.append("_No weaknesses identified — insufficient data._")
        lines.append("")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        log("markdown", f"saved {os.path.basename(path)}")
        return path
    except Exception as e:
        log("markdown", f"failed to write report ({e})", ok=False)
        return ""