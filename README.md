# Get My Flight ✈️

**A Kuwait flight search skill for Claude. Need a ticket from Kuwait? Just ask.**

No more opening ten travel sites and comparing prices by hand. Tell Claude where you want to go, the way you'd tell a friend. It checks the main ticket sites and airlines for you, all at once, and gives you one clear page with the best prices for your whole trip.

It works for **any trip**: a weekend in Dubai, a family holiday in London, Umrah, a honeymoon in the Maldives, or business class to Japan. Going and coming back, one way, into one city and home from another, or several cities in a row.

## Just talk to it

You can ask in your own words, in English or Arabic, for example:

- *"Kuwait to London for the four of us, 10 to 20 December."*
- *"Cheapest business class to Tokyo for 2, around Christmas, a day either side is fine."*
- *"Umrah in March for my parents: into Jeddah, home from Madinah."*
- *"Only Qatar Airways or Kuwait Airways to Istanbul next weekend, nonstop if possible."*
- *"أبي تذاكر لي ولزوجتي لباريس من ٥ إلى ١٥ يناير"*

Claude then asks you a few quick questions, all at once. For *"Dubai on 15 October"*:

> **Claude:** When are you coming back: after 4 days, a week, or another day? What should I call your page, "Kuwait → Dubai, 15–19 Oct" or your own name? And do you want it as a Claude artifact or an HTML file?

That's all. In 10 to 40 seconds you get your ticket page and the best prices in chat.

## What Claude does for you

- **Checks many sites at once:** Google Flights, Almosafer, Flyin, Booking.com, ITA Matrix, Kiwi, and the Qatar Airways and Kuwait Airways fare calendars.
- **Shows the real price.** Every price is the **total for the whole trip**, going and coming back, for everyone travelling. No "from KD 99" surprises.
- **Compares sellers.** The same flight often costs a little more on one site than another. Claude keeps every site's price and tells you which one is cheapest.
- **Picks the best ones:** the cheapest, the best route (fewer stops for a little more), the best nonstop, and the best price on each airline.
- **Handles flexible dates.** Say "a day either side" or "any 10 days in November" and it finds the cheapest days.
- **Warns you about the catches:** a 17-hour wait at a stop, changing airports, two separate tickets, a budget fare with no checked bag, a flight just after midnight.

## Your page

You choose how you get it:

- **Claude artifact:** a link to your page on Claude. Open it anywhere, on your phone too, and share the link with friends.
- **HTML file:** the same page, saved on your computer and opened in Chrome. To share it, send the file.

Either way you get:

- Every ticket with its **airline logo, times, stops and total price**
- **Top picks first**
- **Tap any ticket** to see where it stops, how long you wait there, and a map with the stops marked in red
- Sort by **cheapest, fastest, fewest stops or leaves earliest**
- A price table of every route and date, so you see the cheapest at a glance
- A **Book button** that takes you to the site selling that ticket
- **English and Arabic**, light and dark mode

## Keeps itself working

Travel sites change all the time, so this skill looks after itself:

- **If a site changes,** Claude notices and fixes its part by itself, using the notes it keeps on each site.
- **If one site is slow or down,** the others still answer, and Claude tells you which ones came back empty.
- **Every search is fresh:** prices are at most 20 minutes old, and you can ask for up-to-the-minute prices any time.

## How to install

You need **Claude Code**, in the Claude desktop app or in the terminal.

**The easy way:** open Claude Code and say:

> *Install the skill from https://github.com/majbal87/get-my-flight-kuwait into ~/.claude/skills/get-my-flight*

Claude sets it up for you. Then just ask for a flight. (The very first search takes about a minute longer while it gets ready.)

**If you prefer to do it yourself,** run this once:

```bash
git clone https://github.com/majbal87/get-my-flight-kuwait.git ~/.claude/skills/get-my-flight
```

**Cowork (Claude desktop app):** not tested there yet.

## Good to know

- Works best on a Mac with Google Chrome, where the HTML page opens by itself. It also needs Python 3; if your Mac asks to install it the first time, say yes.
- Searches start from **Kuwait, for 1 adult in economy, with prices in KD**, unless you say otherwise. A few sites only show their own currency.
- Your ticket page is private to you. Nothing is shared unless you send the link or the file.
- Prices change quickly. Always check the final total on the airline or the seller's site before you pay.
- It only finds and compares tickets. It never books, pays or types in anyone's details.
