from __future__ import annotations

from datetime import date
from typing import Any

import httpx
from apify import Actor

try:
    from .core import (
        build_summary,
        build_where_clause,
        comparable_from_record,
        subtract_months,
    )
except ImportError:
    # Permet aussi d'exécuter les fichiers à plat depuis un dépôt créé sur téléphone.
    from core import (
        build_summary,
        build_where_clause,
        comparable_from_record,
        subtract_months,
    )


BODACC_API_URL = (
    "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/"
    "datasets/annonces-commerciales/records"
)


async def fetch_records(where: str, max_records: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = 0
    page_size = 100

    timeout = httpx.Timeout(30.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        while len(records) < max_records:
            limit = min(page_size, max_records - len(records))
            response = await client.get(
                BODACC_API_URL,
                params={
                    "where": where,
                    "order_by": "dateparution desc",
                    "limit": limit,
                    "offset": offset,
                },
                headers={"User-Agent": "PrixCession-France/0.1 (Apify Actor)"},
            )
            response.raise_for_status()
            payload = response.json()
            page = payload.get("results", [])
            if not page:
                break
            records.extend(page)
            offset += len(page)
            if len(page) < limit:
                break

    return records


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        keywords = [
            str(keyword).strip()
            for keyword in actor_input.get("activityKeywords", [])
            if str(keyword).strip()
        ]
        departments = [
            str(department).strip().upper()
            for department in actor_input.get("departments", [])
            if str(department).strip()
        ]
        months_back = int(actor_input.get("monthsBack", 24))
        max_comparables = int(actor_input.get("maxComparables", 40))
        min_price = float(actor_input.get("minPriceEur", 1000))
        max_price = float(actor_input.get("maxPriceEur", 5_000_000))

        if not keywords:
            raise ValueError("Ajoutez au moins un mot-clé d'activité.")
        if min_price >= max_price:
            raise ValueError("Le prix minimum doit être inférieur au prix maximum.")

        today = date.today()
        date_from = subtract_months(today, months_back).isoformat()
        date_to = today.isoformat()
        where = build_where_clause(
            keywords=keywords,
            departments=departments,
            date_from=date_from,
            date_to=date_to,
        )

        # We fetch extra notices because some notices have no reliably extractable price.
        fetch_limit = min(max(max_comparables * 8, 200), 2_000)
        Actor.log.info("Recherche BODACC : %s", where)
        records = await fetch_records(where, fetch_limit)

        comparables: list[dict[str, Any]] = []
        for record in records:
            comparable = comparable_from_record(record, keywords, min_price, max_price)
            if comparable is not None:
                comparables.append(comparable)
            if len(comparables) >= max_comparables:
                break

        summary = build_summary(
            comparables,
            keywords=keywords,
            departments=departments,
            date_from=date_from,
            date_to=date_to,
            scanned_count=len(records),
        )

        # With Apify pay-per-event enabled, dataset items can be billed automatically
        # through the built-in apify-default-dataset-item event.
        await Actor.push_data([summary, *comparables])
        await Actor.set_value("OUTPUT", summary)
        await Actor.charge(event_name="report-generated")
        await Actor.set_status_message(
            f"Terminé : {len(comparables)} comparables trouvés pour {', '.join(keywords)}."
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
