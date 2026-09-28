# Aviasales public price matrix (not working)

**Would be good for:** a cached cheapest-price grid (depart range × return range) in one call.
**Tried 2026-09-27 (GET, Accept: application/json):**
- `https://min-prices.aviasales.ru/calendar_preload?origin=KWI&destination=IST&depart_date=2026-12-10&return_date=2026-12-17&one_way=false` → 404 nginx
- `https://lyssa.aviasales.ru/price_matrix?origin_iata=KWI&destination_iata=IST&depart_start=2026-12-09&depart_range=2&return_start=2026-12-16&return_range=2` → 404
- `https://min-prices.aviasales.ru/price_matrix?…` → 404
Endpoints are gone. The official replacement (`api.travelpayouts.com/v1/prices/calendar`, `/v2/prices/month-matrix`) needs a free Travelpayouts token (sign-up), so not used. OctoTrip wrapped Aviasales live search (archived in round 4: slow, mixes airports).
**Repair idea:** if the user ever signs up, the token-based month-matrix gives cached economy prices per day in one call.
