"""Cleartrip UAE (www.cleartrip.ae) flight prices: same backend, endpoint and encryption key as Flyin
(Cleartrip owns Flyin), so this just calls flyin.search with the .ae host. Sells in AED; KWD = AED x the
rate in the same reply. kw.cleartrip.com redirects to cleartrip.com (India, INR, Akamai) - not used.

CLI: python cleartrip.py KWI-HND:2026-12-19 HND-KWI:2026-12-30 --adults 4 --cabin business
"""
import flyin


def search(legs, adults=1, children=0, infants=0, cabin="economy", currency="KWD", airlines=None):
    return flyin.search(legs, adults, children, infants, cabin, currency, airlines,
                        base_url="https://www.cleartrip.ae", source="cleartrip")


if __name__ == "__main__":
    from almosafer import cli
    cli(search)
