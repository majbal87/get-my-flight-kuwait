---
name: get-my-flight
description: "**Get My Flight (Flight Ticket Search)**: Takes a plain request in English or Arabic ('Kuwait to London for the four of us, 10–20 December'), asks what's still missing in one quick form (where to, dates, the day back, page name, Claude artifact or HTML file), makes a small search plan, and checks many sites at once with fast plain scripts (Google Flights, Almosafer, Flyin, Booking.com, ITA Matrix, a Kiwi date grid, the Qatar Airways and Kuwait Airways fare calendars). Keeps every site's price for the same flights and answers in chat with whole-trip totals for all travellers (going and coming back, never a per-leg price): a price table, the cheapest, the best route, the best nonstop and the best price per airline, with the catches (long waits, airport changes, separate tickets, bags). Then makes a ticket page, as a Claude artifact link or an HTML file opened in Chrome (airline logos, route maps, tap a ticket to see its stops, sort by cheapest / fastest / fewest stops, English / العربية, light and dark) with a Book button to the site selling each ticket. Round trips, one ways, open-jaw, multi-city, flexible dates or a whole month, families, business class. From Kuwait (KWI) in KWD unless told otherwise. TRIGGERS: 'find me flights', 'get my flight', 'cheapest tickets to …', 'how much to fly to …', 'flights for my family to …', 'business class to …', 'Umrah flights', 'أبي تذاكر لـ …'. Only searches: never books, pays or enters anyone's details."
---

# Get My Flight ✈️ (Flight Ticket Search)

Find the best whole-trip ticket prices for a trip, answer in chat, and publish a ticket page the person clicks through to book.
Defaults: from Kuwait (KWI), prices in KWD. This skill only searches: it never books, pays, signs in or types anyone's details.
`SKILL_DIR` = the folder this file is in; everything the skill uses lives there.

## Step 0: Setup
`bash "$SKILL_DIR/scripts/setup.sh"` (makes `SKILL_DIR/.venv` with `primp` only if missing). Run every script with `"$SKILL_DIR/.venv/bin/python"`.

## Step 1: Understand the request
Reply in the customer's language (Arabic in → Arabic out).
| What | Default if not said |
|---|---|
| From | Kuwait (KWI) |
| To | must be given (city, country or region) |
| Dates | must be given: a start date, and a return date or trip length |
| Flexibility | none; "a day either side" = ±1; "flexible" / "around" = ±1–2 days |
| Round trip | always: going and coming back, priced as one whole trip. One date only: ask "When are you coming back (a date or how many days)?", never offer one way. One way only when the customer says so ("one way", "no return") |
| Travellers | 1 adult ("the two of us", honeymoon = 2 adults). Ages: 12+ adult, 2–11 child, under 2 infant on the lap |
| Cabin | economy |
| Airlines | any; "only Qatar" = `airlines`; "I like Qatar", "Qatar, Etihad or Kuwait Airways" = `prefer` |
| Sellers | the default sites; "all sites" / "every seller" = `"sellers": "all"` |
| Currency | KWD (best tested), also for people outside Kuwait unless they ask for another |

- **Places:** a country = the airports of its 1–2 main cities (Japan = Tokyo HND, NRT + Osaka KIX). A region = its airports: Kerala = COK, CCJ, TRV; Bali = DPS; Maldives = MLE; Umrah = into JED, home from MED possible (open-jaw). Say which airports you chose.
- **A month only** ("in December"): ask the dates. **Month + length** ("December for 10 days"): ask the start day, or offer a month search (cheapest start day in that month).
- **"Next weekend"** = the coming Friday–Saturday (Kuwait weekend); Thursday-night departures are common. Say the dates you assumed.
- **Holidays** (Eid, Ramadan, National Day): ask them to confirm the dates, giving your estimate in the question ("Eid al-Fitr 2027 is expected around 9 March: which days do you want to fly?").
- **"Next Monday"** = the coming Monday (said on a Monday: in 7 days); **"end of the month"** = its last 7 days as a window. Say the dates you assumed.
- **Vague place** ("somewhere warm in Europe"): offer 2–3 places as choices (the "Where" question below). **A budget:** say which options fit it.
- **Language:** reply in the customer's language (mostly Arabic → Arabic).
- **A past date**, or more than 330 days ahead: point it out and ask.
- **A window + a length** ("first week of December, 5 nights"): one trip per start day in the window (same length each, up to 7); `flex_days` would change the length.
- **Times in words:** "morning" = `depart_before` 12:00, "evening" / "at night" = `depart_after` 18:00; a time wish covers both directions unless they said which.
- **Their own words:** two return dates they gave ("back on the 29th or 30th") = exactly those two, called "the two return dates you gave", not "±1 day".
- **Two cabins** ("economy and business"): two plans in two run folders. **A different cabin per leg** (business only on the long flight): one plan per cabin with those legs as one-way trips; say they are separate tickets.
- **"Arrive by <date>"**: set the flight date so the arrival fits (long westbound flights land the same or next day) and say it; "not in the middle of the night" = `depart_after` 06:00. **More than 9 seats** (adults + children): one booking takes at most 9; say so and split into two plans, keeping families together (each lap infant with an adult in its plan); answer with each plan's pick on the same flights and the total as your own sum.
- **Another currency** (SAR, USD…): allowed, but prices from sites that can't give it are left out (a note in the run); tell the customer.
- **Ask in one form.** If the request says little ("find me a flight"), ask in plain words: "Where would you like to go, and when?" and wait for the answer. Then ask everything still missing in **one** `AskUserQuestion` call (at most 4 questions, 2–4 choices each, an "Other" is added for exact words; with 5 needed, fold the page type into the page-name question: "What should this page be called? (a Claude artifact link unless you say HTML file)"), in the customer's language, in this order, dropping what they already said:
  1. **Where**, only for a vague place: 2–3 places as choices.
  2. **When**, if the dates are missing: likely dates as choices. A month only, a holiday (your estimate in the question), a past date or one more than 330 days ahead is asked here.
  3. **"When are you coming back?"**, when only the going date was given (never with question 2, which asks both ends): choices by length with the real weekday ("After 4 days: Mon 19 Oct", "After a week: Thu 22 Oct").
  4. **"What should this page be called?"** (always). It may be for someone else, so offer a name from the trip ("Kuwait → Dubai, 15–19 Oct", Recommended; only what's already known, e.g. "Kuwait → Dubai Trip" while the dates are still being asked), a person's name ("My Parents' Umrah" when it's for them, else "My Dubai Trip", with "Ahmad's Dubai Trip" as an example in its description) and a title of its own ("Family Weekend in Dubai"); "Other" for the exact words. Write the options, and "Recommended", in their language. Skip it only when they already named the page.
  5. **"How do you want your page?"** (always, unless they said): **Claude artifact** (Recommended): "a link you can open anywhere and share with friends; it's viewed online" / **HTML file**: "saved on this computer and opened in Chrome; to share it, you send the file itself; there's no online link". In their language.
  Never ask what has a default (travellers, cabin, from Kuwait, currency): the reading line states them.
- **Vague answers** ("around the 10th", "whatever's cheapest"): don't ask again. Use the defaults and your own judgment, note what you decided, and explain it at the end (Step 5, "How I read your request").
- **State your reading in one line and continue**, with the count and time from Step 2: "Kuwait → Dubai, 15–19 Oct, 1 adult, economy, page "Kuwait → Dubai, 15–19 Oct" (Claude artifact). I'll check 1 option, about 10 seconds."

## Step 2: Make a small search plan
One **trip** = one set of legs on fixed dates.
- **City → airports**, each its own trip with the same `route` (one matrix column per city): London = LHR, LGW (STN only when a budget airline is wanted or named). Tokyo = HND, NRT. Osaka = KIX. Paris = CDG. Rome = FCO. Milan = MXP. Istanbul = IST, SAW. New York = JFK, EWR. Dubai = DXB. Bangkok = BKK. Else the one main airport. Several airports at both ends (London ⇄ New York): only the main pair (LHR–JFK) unless asked.
- **Dates:** fixed = one trip per date pair given. Flexible round trip / one way = one trip with their dates plus `flex_days` (search.py adds the cheap pairs itself). Flexible open-jaw or multi-city: add the date pairs yourself as trips (both dates −1 and both +1); `flex_days` is ignored there.
- **Two cities in one country** ("Tokyo and Osaka", or a country with two main cities): a round trip to each, plus open-jaw trips (into one, home from the other) both ways round, only when they didn't fix the direction ("into Osaka, home from Tokyo" = that one only). Don't search the hop between the cities.
- **3+ legs** (Paris, then London, then home): one trip with all legs in date order, plus each leg as its own one-way trip (separate tickets are often cheaper or nonstop; their sum is your own sum). Two separate one-way tickets asked: two one-way trips.
- **Keep it small:** 12 trips or fewer; over 20, cut dates or airports, or ask.
- **The time** goes in the reading line (Step 1), with the count: "I'll check 8 options (4 routes × 2 date pairs), about 20 seconds." Time ≈ 2.5 s × trips (a `flex_days` trip counts as 4), at least 10 s, plus 15 s for each route with `flex_days`, plus 3 s for open-jaw / multi-city trips. So 1 trip ≈ 10 s, 3–4 trips ≈ 15–25 s (Almosafer answers 2 at a time), 10 trips ≈ 25–35 s, 2 flex trips on one route ≈ 35 s. Never promise more than "up to 3 minutes".

Write `SKILL_DIR/runs/<YYYY-MM-DD>-<short-name>/plan.json`:
```json
{"title": "Kuwait → Japan Fares", "adults": 4, "children": 0, "child_ages": [], "infants": 0, "cabin": "business",
 "currency": "KWD", "airlines": null, "prefer": ["QR"],
 "trips": [
  {"label": "Tokyo round trip, 19–30 Dec", "route": "Tokyo round trip", "flex_days": 1,
   "legs": [{"from": "KWI", "to": "HND", "date": "2026-12-19", "depart_after": "18:00"}, {"from": "HND", "to": "KWI", "date": "2026-12-30"}]},
  {"label": "Osaka in, Tokyo out, 19–30 Dec", "route": "Osaka in, Tokyo out",
   "legs": [{"from": "KWI", "to": "KIX", "date": "2026-12-19"}, {"from": "HND", "to": "KWI", "date": "2026-12-30"}]}]}
```
- `title`: the page name from Step 1, in their exact words ("don't mind" = the name from the trip). `title_ar`: the same name in Arabic for the page's Arabic side (a person's name kept as a name: "رحلة أحمد إلى دبي"); leave it out for a name from the trip, which the page translates itself. `label`: optional (made from the legs); say "round trip", never "return" (it reads as the flight back only). Dates `YYYY-MM-DD`, legs in date order.
- `cabin`: `economy` | `premium` | `business` | `first` ("premium economy" = `premium`).
- Travellers: `child_ages` = one real age per child (sets `children`; if you also give `children`, it must match). Ages 12+ are counted as adults; a child under 2 goes in `infants` (lap), not in `child_ages`. `infants` ≤ `adults`; adults + children ≤ 9 (lap infants don't count).
- `currency`: `KWD` unless asked (see Step 1).
- `airlines`: IATA codes when they want **only** those (then not also in `prefer`); else `null`. `prefer`: airlines they like or named; the search stays open to all.
- Named airlines (either field) get their own fare calendar when they have one (Qatar: adults only, economy/business; Kuwait Airways: no infants, economy/business), Flyin as an extra seller, and a page line with each one's best price and site. `"sellers": "all"` adds Flyin even with no airline named.
- `flex_days` (per round-trip / one-way trip): `N` = ±N days both ends (0–10); `[out, back]` = each end on its own (`[0, 3]` = leave on the day, return ±3); `"month"` = any start day in the month of the trip's first date, a return keeping its length. Month search, e.g. November for 10 days: legs 2026-11-01 and 2026-11-11 with `"flex_days": "month"` (that start date only names the month; the month search picks the days).
- **Wishes** (only when they said so; "nonstop if possible" is not a wish: leave `nonstop` off, the best nonstop is always shown): `"nonstop": true`; `"max_layover_h": N` (hours); `"bags": N` (checked bags per person they need; carry-on only = leave it out); per leg `"depart_after"` / `"depart_before"` / `"arrive_before"`: `"HH:MM"` (local time, on that leg's date). Options that miss a wish are shown with a note and kept out of the picks.

## Step 3: Search
```bash
cd "$SKILL_DIR/runs/<folder>" && "$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/search.py" plan.json results.json 2>&1 | tee run.log
```
Bash timeout 240000 ms. It prints one line per search, "5/12 done", then a summary. Which sites run for which trip, time limits and merge rules: the top of `scripts/search.py`.
- It stops with "plan.json: …" when the plan can't be searched: fix the plan as the message says and rerun.
- Answers are cached 20 minutes (a repeat answers in ~1 s); add `--fresh` for up-to-the-minute prices.
- A trip with no price is **unknown**, not "no flights"; so is a site's "no answer in time". Say which trips came back empty and from which sources.
- A "dropped …: not the plan's currency" note = that site can't price in that currency; tell the customer (Toolbox: cleartrip.py prices in AED).
- An Almosafer note "may be missing from Almosafer's round-trip list; its one-way pages sell these flights" = on Almosafer, book it as two one-ways (the price can differ by a few KD).
- "no J9 fares found on …" = those sites answered but sell none of that airline for these dates: say so and offer to search all airlines.
- The run took much longer than you said? Say so (run.log shows the slow site).

## Step 4: Build and publish the page
```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/make_page.py" results.json page.html
```
It writes the page and prints the matrix, the picks and the per-airline list (used in Step 5). Then, as they chose in Step 1:
- **Claude artifact:** publish `page.html` with the Artifact tool (`icon` = "flight", a one-sentence `description` like "Whole-trip business fares for 4 from Kuwait to Japan, 19–31 Dec 2026").
- **HTML file:** the same page as a complete file, saved in the skill and opened in Chrome (the page name as the file name, without `/` or `:`):
  ```bash
  mkdir -p "$SKILL_DIR/pages" && "$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/make_page.py" results.json "$SKILL_DIR/pages/<page name>.html" --file && open -a "Google Chrome" "$SKILL_DIR/pages/<page name>.html"
  ```
  No Chrome: `open` the file instead. It needs the internet only for the fonts; everything else is inside the file.

## Step 5: Reply
1. **Lead with the page link** and its name (an HTML file: its path, already open in Chrome, and "to share it, send this file").
2. **A short picks table:** each Top pick with its labels ("Cheapest · Best route · Best nonstop"), airline, stops, whole-trip total, the cheapest site, and why in a few words.
   - A pick that wins several boxes: say it wins all of them. "No nonstop found on this route" on the top pick: say plainly that every option has a stop.
   - "2nd cheapest airline" / "3rd cheapest airline" picks (there are always at least 3 choices) are the next options.
3. **The matrix** of whole-trip totals, when there is more than one trip or date pair (paste it). `*` = not a normal ticket; `[KD 7,301*]` = a cheaper flagged option exists.
4. **Under the table**, only what applies:
   - **Cheapest:** the other sites' prices for the same flights; name every "Same price: …" line.
   - **Best route:** fewest stops / shortest time within 15% of the cheapest; one line on why it may be worth it (a nonstop for KD 20 more for a family of four usually is).
   - **Best nonstop:** always mention it, even when dear, or say none was found (the Booking.com fallback is "flights on the Booking.com link").
   - **Best price per airline:** for each named airline, its best price and site. "Feeder only" = it flies just a short connection (e.g. KWI→DOH before Qatar's long flight): say it doesn't fly the whole route and name the airline that flies the long leg. None named: the list shows the 8 cheapest airlines (a mix of airlines counts under the one flying the longest flight; a row that misses a wish carries its note).
5. **Lines above the picks:** "No <cabin> found for the whole trip on this route; the options mix cabins" = say that cabin isn't sold on this route and offer the next one (first → business, premium → economy). "No prices came back for …" = say which sites answered what; never let an empty site look like no flights.
6. **Wishes:** "fits your wishes: …" on a pick = say it meets them. "doesn't match your wish: …" = say what misses. "Nothing found matches your wishes (…)" = say so plainly first, then give the "Closest options (each misses a wish)" and what each misses.
7. **The catches**, as short bullets from each pick's notes: "flown by …" (another airline flies the plane) and "(sold as …)"; "just after midnight: the night of …" (be at the airport the evening before); "Bags: …" (checked bags or "cabin bag only"; "Bags: Almosafer: …" = another site selling the same fare stated them); "Cheapest with your bags confirmed: …" (say it when they need bags); "a 17h wait in AUH" (a long wait: say it); "2 one-way fares" (out and back are two bookings, changed or cancelled separately); "separate tickets" (a self-transfer: a missed connection is their risk); "priced in …, not compared" (another currency). "bags not stated: check before booking". "Cheaper on Google Flights (return flights not shown; confirm the total there): …" = mention it as cheaper but unconfirmed, never as the pick. "(its Book button lists the airline/agency sellers)" = Google Flights doesn't sell tickets: they book with the seller shown there (airline direct is safer). "Cheapest (SYD → KUL)" = the plan's one-way trips are legs of one journey: give each leg's pick and their sum as your own sum. "Only part of the trip (…)" next to an airline = it has no ticket on every leg. A "(note: …)" on a pick means every option had a flag (e.g. a mixed cabin): say it.
8. Open-jaw / multi-city Book links open the site's results list: tell them to pick the flight numbers shown on the card.
9. "Prices change quickly. Check the final total on the airline or Google page before paying." The page follows their light or dark setting and has English / العربية and Light / Dark switches.
10. Last, only when you had to judge a vague request: **"How I read your request"**, 2–4 short lines (airports chosen, dates assumed, travellers and cabin used, and why).

Changes later ("what about business?", "a day later"): edit plan.json, rerun Steps 3–4 in the same folder and republish to the same page (or rewrite the same file). A new page name: set `title` (and `title_ar`) in plan.json and results.json and rerun Step 4 (a file gets the new name; delete the old one). Switching between artifact and file: rerun Step 4 the other way; no new search.

Rules for prices:
- Always the **whole-trip total for all travellers**; never a per-leg or per-person price as the total. Anything you work out yourself, say it is your own sum.
- Name the site for each price and whether it is the airline direct or a travel agency (direct is safer if plans change; check an agency's reviews). "≈ … (converted from SAR)" is a converted price: fine for comparing, the exact total is on the site. ITA Matrix can't sell tickets: book on the airline's site or Google Flights.
- Google round trips show the outbound flights only; the price is still the whole trip, the return is on the Google link. A Google round-trip price no other site confirmed is flagged (it can be 10–18% low).
- Budget airlines (Jazeera, flynas, Air Arabia, Pegasus, flydubai…), economy/premium: the script adds "checked bags usually cost extra"; say it.
- Say when prices were fetched (`fetched_at` per trip; the page header shows the range) and the age of cached ones (`cached_min`).
- Asked what a flag means? An airport change inside a connection, a hop between the two cities of an open-jaw, a lower cabin on one flight, separate tickets (self-transfer), a converted price only, an unconfirmed Google round trip, or a missed wish; all are kept out of the picks.

## Toolbox: when the default search leaves gaps
An airline, route or airport is missing, a source failed, or a price looks wrong:
1. `SKILL_DIR/references/sources/README.md` lists every source (speed, currency, trip types, exact or converted); then read that source's card.
2. Call one source directly; every script takes the same arguments and prints the same JSON search.py uses, e.g.
   `"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/booking.py" KWI-KIX:2026-12-19 HND-KWI:2026-12-30 --adults 4 --cabin business --airlines QR`
   Calendars and hints (qatar, kuwaitairways, everymundo, kiwi_grid) reply per date: see their cards. Hints are per adult, never a total.
3. Add what you found to the answer (name the source), or add the trip to plan.json and rerun Steps 3–4 (cached trips answer in 1 s).
4. A broken script: repair it with its card's "Broken?" steps, test it with its CLI, note the change in the card. Never use a browser for searching.

## Airlines
`references/airlines.md` lists airlines seen from Kuwait; add a line for a new one. An airline the person asked for that doesn't appear: say it wasn't in the results for that search; don't guess why.
