"""Arabic for the flight page: translate(html) returns the same HTML with every visible English text node (and every
aria-label) in Arabic. Tags, classes, ids, URLs, <style>, <script> and SVG path data are never touched.

How: each text node is unescaped, then goes through
  1. EXACT     whole short nodes ("Out" -> "ذهاب", "Book" -> "احجز"),
  2. PHRASES   fixed sentences and pieces of sentences,
  3. NAMES     airlines, the Almosafer site, cities and countries (whole names, longest first:
               "Kuwait Airways" before "Kuwait", "Istanbul Sabiha" before "Istanbul"),
  4. RULES     ordered (regex, replacement) rules: money, durations, counts, dates, leg words,
  5. tidy()    Arabic commas, and "→" turned to "←" in Arabic text (the page reads right to left),
and is escaped again. Western digits, times, flight numbers, airport codes and booking-site names stay as they are.
Anything no rule covers stays English.
"""
import re
from html import escape, unescape

# ---------- names ----------
AIRLINES = {  # every name in make_page.NAMES, plus the other spellings sources use
    "Kuwait Airways": "الخطوط الجوية الكويتية", "Kuwait Airways Corp": "الخطوط الجوية الكويتية",
    "Jazeera Airways": "طيران الجزيرة", "Qatar Airways": "الخطوط الجوية القطرية", "Emirates": "طيران الإمارات",
    "Emirates Airlines": "طيران الإمارات", "flydubai": "فلاي دبي", "Fly Dubai": "فلاي دبي", "Flydubai": "فلاي دبي",
    "Etihad Airways": "الاتحاد للطيران", "Etihad": "الاتحاد للطيران", "Gulf Air": "طيران الخليج",
    "Oman Air": "الطيران العماني", "SalamAir": "طيران السلام", "Salam Air": "طيران السلام",
    "Saudia": "الخطوط السعودية", "Saudi Arabian Airlines": "الخطوط السعودية", "flynas": "طيران ناس",
    "Flynas": "طيران ناس", "flyadeal": "طيران أديل", "Air Arabia": "العربية للطيران",
    "Air Arabia Abu Dhabi": "العربية للطيران أبوظبي", "Air Arabia Egypt": "العربية للطيران مصر",
    "Air Arabia Maroc": "العربية للطيران المغرب", "MEA (Middle East Airlines)": "طيران الشرق الأوسط",
    "Middle East Airlines": "طيران الشرق الأوسط", "Royal Jordanian": "الملكية الأردنية", "EgyptAir": "مصر للطيران",
    "Egyptair": "مصر للطيران", "Nile Air": "طيران النيل", "Air Cairo": "إير كايرو", "Nesma Airlines": "طيران نسما",
    "Fly Baghdad": "فلاي بغداد", "Iraqi Airways": "الخطوط الجوية العراقية", "Turkish Airlines": "الخطوط الجوية التركية",
    "Pegasus": "طيران بيغاسوس", "Pegasus Airlines": "طيران بيغاسوس", "AJet": "أجيت", "SunExpress": "صن إكسبريس",
    "Air India": "طيران الهند", "Air India Express": "طيران الهند إكسبريس", "IndiGo": "إنديغو",
    "SpiceJet": "سبايس جت", "Akasa Air": "أكاسا إير", "Pakistan International Airlines": "الخطوط الجوية الباكستانية",
    "airblue": "إيربلو", "AirSial": "إير سيال", "Fly Jinnah": "فلاي جناح", "SereneAir": "سيرين إير",
    "Biman Bangladesh": "بيمان بنغلاديش", "Biman Bangladesh Airlines": "بيمان بنغلاديش",
    "US-Bangla Airlines": "يو إس بنغلا", "SriLankan Airlines": "الخطوط الجوية السريلانكية",
    "Nepal Airlines": "الخطوط الجوية النيبالية", "Philippine Airlines": "الخطوط الجوية الفلبينية",
    "Cebu Pacific": "سيبو باسيفيك", "Malaysia Airlines": "الخطوط الجوية الماليزية", "AirAsia": "طيران آسيا",
    "AirAsia X": "طيران آسيا إكس", "Thai Airways": "الخطوط الجوية التايلاندية", "Thai AirAsia": "طيران آسيا تايلاند",
    "Singapore Airlines": "الخطوط الجوية السنغافورية", "Scoot": "سكوت", "Garuda Indonesia": "جارودا إندونيسيا",
    "Vietnam Airlines": "الخطوط الجوية الفيتنامية", "Cathay Pacific": "كاثي باسيفيك",
    "ANA": "طيران أول نيبون (ANA)", "All Nippon Airways": "طيران أول نيبون (ANA)",
    "Japan Airlines": "الخطوط الجوية اليابانية", "Korean Air": "الخطوط الجوية الكورية",
    "Asiana Airlines": "طيران آسيانا", "Air China": "طيران الصين", "China Eastern": "طيران الصين الشرقية",
    "China Eastern Airlines": "طيران الصين الشرقية", "China Southern": "طيران الصين الجنوبية",
    "China Southern Airlines": "طيران الصين الجنوبية", "Shanghai Airlines": "طيران شنغهاي",
    "Hainan Airlines": "طيران هاينان", "Ethiopian Airlines": "الخطوط الجوية الإثيوبية",
    "Kenya Airways": "الخطوط الجوية الكينية", "Royal Air Maroc": "الخطوط الملكية المغربية",
    "Tunisair": "الخطوط التونسية", "Air Algerie": "الخطوط الجوية الجزائرية",
    "British Airways": "الخطوط الجوية البريطانية", "Lufthansa": "لوفتهانزا", "SWISS": "الخطوط الجوية السويسرية",
    "Austrian Airlines": "الخطوط الجوية النمساوية", "Air France": "الخطوط الجوية الفرنسية",
    "KLM": "الخطوط الجوية الملكية الهولندية", "ITA Airways": "إيتا إيرويز", "Aegean Airlines": "طيران إيجه",
    "Iberia": "أيبيريا", "Air Europa": "إير أوروبا", "SAS": "الخطوط الجوية الإسكندنافية",
    "LOT Polish Airlines": "الخطوط الجوية البولندية", "Condor": "كوندور", "Wizz Air": "ويز إير",
    "Wizz Air Abu Dhabi": "ويز إير أبوظبي", "Ryanair": "رايان إير", "easyJet": "إيزي جت",
    "American Airlines": "الخطوط الجوية الأمريكية", "United Airlines": "يونايتد إيرلاينز",
    "Delta Air Lines": "دلتا إيرلاينز", "Air Canada": "طيران كندا", "Air Astana": "طيران أستانا",
    "Virgin Australia": "فيرجن أستراليا", "Air Dolomiti": "إير دولوميتي",
    "Jetstar": "جت ستار", "Jetstar Airways": "جت ستار", "Jetstar Japan": "جت ستار اليابان", "Batik Air": "باتيك إير",
    "Vietjet": "فيت جت", "VietJet Air": "فيت جت", "Vueling": "فويلينغ", "Easyjet": "إيزي جت",
    "Porter Airlines": "بورتر إيرلاينز", "Greater Bay Airlines": "طيران غريتر باي", "Juneyao Airlines": "طيران جونياو",
    "Hong Kong Airlines": "طيران هونغ كونغ", "Norwegian Air": "الطيران النرويجي", "Norwegian": "الطيران النرويجي",
    "Eva Airways": "إيفا إير", "EVA Air": "إيفا إير", "Qantas": "كانتاس", "Virgin Atlantic": "فيرجن أتلانتيك",
    "Air Serbia": "طيران صربيا", "Vistara": "فيستارا", "Xiamen Airlines": "طيران شيامن", "Sichuan Airlines": "طيران سيتشوان",
    "Air New Zealand": "طيران نيوزيلندا", "Aeroflot": "إيروفلوت", "Azerbaijan Airlines": "الخطوط الجوية الأذربيجانية",
    "Uzbekistan Airways": "الخطوط الجوية الأوزبكية", "Starlux Airlines": "ستارلوكس", "Air Seychelles": "طيران سيشل",
    "Air Mauritius": "طيران موريشيوس", "RwandAir": "الخطوط الرواندية", "Air Tanzania": "طيران تنزانيا",
}
SITES = {"Almosafer": "المسافر"}  # every other booking site keeps its Latin name
CITIES = {  # every city in make_page.AIRPORTS, plus plain city and country names used in trip labels
    "Kuwait": "الكويت", "Dubai": "دبي", "Dubai World Central": "دبي وورلد سنترال", "Abu Dhabi": "أبوظبي",
    "Sharjah": "الشارقة", "Ras Al Khaimah": "رأس الخيمة", "Doha": "الدوحة", "Bahrain": "البحرين", "Muscat": "مسقط",
    "Salalah": "صلالة", "Riyadh": "الرياض", "Jeddah": "جدة", "Dammam": "الدمام", "Madinah": "المدينة المنورة",
    "Abha": "أبها", "Taif": "الطائف", "Tabuk": "تبوك", "Qassim": "القصيم", "Amman": "عمّان", "Beirut": "بيروت",
    "Baghdad": "بغداد", "Basra": "البصرة", "Erbil": "أربيل", "Najaf": "النجف", "Sulaymaniyah": "السليمانية",
    "Damascus": "دمشق", "Cairo": "القاهرة", "Cairo Sphinx": "القاهرة سفنكس", "Alexandria": "الإسكندرية",
    "Sharm El Sheikh": "شرم الشيخ", "Hurghada": "الغردقة", "Luxor": "الأقصر", "Tehran": "طهران",
    "Mashhad": "مشهد", "Istanbul": "إسطنبول", "Istanbul Sabiha": "إسطنبول صبيحة", "Ankara": "أنقرة",
    "Izmir": "إزمير", "Antalya": "أنطاليا", "Trabzon": "طرابزون", "Bodrum": "بودروم", "Dalaman": "دالامان",
    "Delhi": "دلهي", "Mumbai": "مومباي", "Bengaluru": "بنغالورو", "Chennai": "تشيناي", "Hyderabad": "حيدر آباد",
    "Kochi": "كوتشي", "Thiruvananthapuram": "تيروفانانثابورام", "Kozhikode": "كوزيكود", "Kannur": "كانور",
    "Mangaluru": "مانغالور", "Kolkata": "كولكاتا", "Ahmedabad": "أحمد آباد", "Goa": "غوا", "Goa Mopa": "غوا موبا",
    "Lucknow": "لكناو", "Amritsar": "أمريتسار", "Jaipur": "جايبور", "Karachi": "كراتشي", "Lahore": "لاهور",
    "Islamabad": "إسلام آباد", "Peshawar": "بيشاور", "Sialkot": "سيالكوت", "Multan": "ملتان", "Dhaka": "دكا",
    "Chittagong": "شيتاغونغ", "Sylhet": "سيلهت", "Colombo": "كولومبو", "Kathmandu": "كاتماندو", "Malé": "ماليه",
    "Bangkok": "بانكوك", "Bangkok Don Mueang": "بانكوك دون موينغ", "Phuket": "بوكيت", "Kuala Lumpur": "كوالالمبور",
    "Singapore": "سنغافورة", "Jakarta": "جاكرتا", "Bali": "بالي", "Manila": "مانيلا", "Cebu": "سيبو",
    "Ho Chi Minh City": "مدينة هو تشي منه", "Hanoi": "هانوي", "Hong Kong": "هونغ كونغ", "Taipei": "تايبيه",
    "Beijing": "بكين", "Beijing Daxing": "بكين داشينغ", "Shanghai Pudong": "شنغهاي بودونغ",
    "Shanghai Hongqiao": "شنغهاي هونغتشياو", "Guangzhou": "قوانغتشو", "Chengdu": "تشنغدو",
    "Tokyo Narita": "طوكيو ناريتا", "Tokyo Haneda": "طوكيو هانيدا", "Osaka Kansai": "أوساكا كانساي",
    "Osaka Itami": "أوساكا إيتامي", "Nagoya": "ناغويا", "Fukuoka": "فوكوكا", "Sapporo": "سابورو",
    "Seoul Incheon": "سيول إنتشون", "Seoul Gimpo": "سيول غيمبو", "Tashkent": "طشقند", "Almaty": "ألماتي",
    "Astana": "أستانا", "Baku": "باكو", "Tbilisi": "تبليسي", "Yerevan": "يريفان", "London Heathrow": "لندن هيثرو",
    "London Gatwick": "لندن غاتويك", "London Stansted": "لندن ستانستد", "London Luton": "لندن لوتون",
    "London City": "لندن سيتي", "Manchester": "مانشستر", "Birmingham": "برمنغهام", "Edinburgh": "إدنبرة",
    "Glasgow": "غلاسكو", "Dublin": "دبلن", "Paris CDG": "باريس CDG", "Paris Orly": "باريس أورلي", "Nice": "نيس",
    "Lyon": "ليون", "Frankfurt": "فرانكفورت", "Munich": "ميونخ", "Berlin": "برلين", "Düsseldorf": "دوسلدورف",
    "Hamburg": "هامبورغ", "Cologne": "كولونيا", "Amsterdam": "أمستردام", "Brussels": "بروكسل", "Zurich": "زيورخ",
    "Geneva": "جنيف", "Vienna": "فيينا", "Prague": "براغ", "Budapest": "بودابست", "Warsaw": "وارسو", "Rome": "روما",
    "Milan Malpensa": "ميلانو مالبينسا", "Milan Linate": "ميلانو ليناتي", "Venice": "البندقية", "Naples": "نابولي",
    "Madrid": "مدريد", "Barcelona": "برشلونة", "Málaga": "مالقة", "Lisbon": "لشبونة", "Porto": "بورتو",
    "Athens": "أثينا", "Thessaloniki": "سالونيك", "Mykonos": "ميكونوس", "Santorini": "سانتوريني",
    "Copenhagen": "كوبنهاغن", "Stockholm": "ستوكهولم", "Oslo": "أوسلو", "Helsinki": "هلسنكي",
    "Moscow Sheremetyevo": "موسكو شيريميتيفو", "Moscow Domodedovo": "موسكو دوموديدوفو",
    "St Petersburg": "سانت بطرسبرغ", "Sarajevo": "سراييفو", "Tivat": "تيفات", "Podgorica": "بودغوريتسا",
    "Larnaca": "لارنكا", "Malta": "مالطا", "Bucharest": "بوخارست", "Sofia": "صوفيا", "Belgrade": "بلغراد",
    "Zagreb": "زغرب", "Addis Ababa": "أديس أبابا", "Nairobi": "نيروبي", "Johannesburg": "جوهانسبرغ",
    "Cape Town": "كيب تاون", "Dar es Salaam": "دار السلام", "Zanzibar": "زنجبار", "Entebbe": "عنتيبي",
    "Casablanca": "الدار البيضاء", "Marrakesh": "مراكش", "Tunis": "تونس", "Algiers": "الجزائر",
    "Khartoum": "الخرطوم", "Lagos": "لاغوس", "Accra": "أكرا", "Seychelles": "سيشل", "Mauritius": "موريشيوس",
    "New York JFK": "نيويورك JFK", "Newark": "نيوارك", "New York LaGuardia": "نيويورك لاغوارديا",
    "Washington Dulles": "واشنطن دالاس", "Washington Reagan": "واشنطن ريغان", "Boston": "بوسطن",
    "Chicago": "شيكاغو", "Atlanta": "أتلانتا", "Miami": "ميامي", "Orlando": "أورلاندو", "Dallas": "دالاس",
    "Houston": "هيوستن", "Los Angeles": "لوس أنجلوس", "San Francisco": "سان فرانسيسكو", "Seattle": "سياتل",
    "Detroit": "ديترويت", "Philadelphia": "فيلادلفيا", "Toronto": "تورنتو", "Montreal": "مونتريال",
    "Vancouver": "فانكوفر", "Mexico City": "مكسيكو سيتي", "São Paulo": "ساو باولو", "Sydney": "سيدني",
    "Melbourne": "ملبورن", "Brisbane": "بريزبن", "Perth": "بيرث", "Auckland": "أوكلاند",
    # plain names in trip labels, and towns from assets/airports.tsv seen on pages
    "London": "لندن", "Tokyo": "طوكيو", "Osaka": "أوساكا", "Paris": "باريس", "Milan": "ميلانو", "Seoul": "سيول",
    "Shanghai": "شنغهاي", "Moscow": "موسكو", "Washington": "واشنطن", "New York": "نيويورك", "Male": "ماليه",
    "Paphos": "بافوس", "Sohag": "سوهاج", "Mecca": "مكة", "Makkah": "مكة", "Medina": "المدينة المنورة",
    "Japan": "اليابان", "Turkey": "تركيا", "Egypt": "مصر", "India": "الهند", "Thailand": "تايلاند",
    "Georgia": "جورجيا", "Italy": "إيطاليا", "France": "فرنسا", "Spain": "إسبانيا", "Greece": "اليونان",
    "Germany": "ألمانيا", "Malaysia": "ماليزيا", "Indonesia": "إندونيسيا", "Philippines": "الفلبين",
    "Sri Lanka": "سريلانكا", "Nepal": "نيبال", "Pakistan": "باكستان", "Bangladesh": "بنغلاديش",
    "Saudi Arabia": "السعودية", "UAE": "الإمارات", "Qatar": "قطر", "Oman": "عُمان", "Jordan": "الأردن",
    "Lebanon": "لبنان", "Iraq": "العراق", "Iran": "إيران", "Azerbaijan": "أذربيجان", "Armenia": "أرمينيا",
    "Kazakhstan": "كازاخستان", "Uzbekistan": "أوزبكستان", "UK": "المملكة المتحدة", "USA": "الولايات المتحدة",
    "Canada": "كندا", "Australia": "أستراليا", "Korea": "كوريا", "China": "الصين", "Maldives": "المالديف",
    "Europe": "أوروبا", "Cyprus": "قبرص", "Morocco": "المغرب", "Kenya": "كينيا", "Tanzania": "تنزانيا",
    "Bosnia": "البوسنة", "Montenegro": "الجبل الأسود", "Switzerland": "سويسرا", "Austria": "النمسا",
    "Suhaj": "سوهاج", "Calicut": "كاليكوت", "Bilbao": "بلباو", "Kunming": "كونمينغ", "Malaga": "مالقة",
    "Kerala": "كيرالا",
}
NAMES = {**CITIES, **SITES, **AIRLINES}
NAME_RE = re.compile(r"(?<!\w)(%s)(?!\w)(?! Airlines| Airways| Air\b)" % "|".join(
    re.escape(n) for n in sorted(NAMES, key=len, reverse=True)))

WEEKDAYS = {"Mon": "الاثنين", "Tue": "الثلاثاء", "Wed": "الأربعاء", "Thu": "الخميس", "Fri": "الجمعة",
            "Sat": "السبت", "Sun": "الأحد"}
MONTHS = {"Jan": "يناير", "Feb": "فبراير", "Mar": "مارس", "Apr": "أبريل", "May": "مايو", "Jun": "يونيو",
          "Jul": "يوليو", "Aug": "أغسطس", "Sep": "سبتمبر", "Oct": "أكتوبر", "Nov": "نوفمبر", "Dec": "ديسمبر"}
CABINS = {"premium economy": "الدرجة الاقتصادية المميزة", "economy": "الدرجة الاقتصادية",
          "business class": "درجة رجال الأعمال", "first class": "الدرجة الأولى", "premium": "الاقتصادية المميزة",
          "business": "رجال الأعمال", "first": "الأولى"}
LABEL_WORDS = {  # free words people put in trip labels ("Kuwait → Dubai Weekend", "Lahore one way, late Nov")
    "January": "يناير", "February": "فبراير", "March": "مارس", "April": "أبريل", "June": "يونيو", "July": "يوليو",
    "August": "أغسطس", "September": "سبتمبر", "October": "أكتوبر", "November": "نوفمبر", "December": "ديسمبر",
    "early": "أوائل", "mid": "منتصف", "late": "أواخر", "around": "حوالي", "about": "حوالي", "Family": "رحلة عائلية",
    "Weekend": "عطلة نهاية الأسبوع", "Day Trip": "رحلة يوم واحد", "day trip": "رحلة يوم واحد", "Honeymoon": "شهر العسل",
    "Winter": "الشتاء", "Summer": "الصيف", "Umrah": "عمرة", "Ramadan": "رمضان", "Business": "درجة رجال الأعمال",
    "First": "الدرجة الأولى", "Return": "ذهاب وعودة", "same day": "في نفس اليوم", "night before": "الليلة السابقة",
    "(economy)": "(الدرجة الاقتصادية)", "(business)": "(درجة رجال الأعمال)", "(first)": "(الدرجة الأولى)",
    "(premium economy)": "(الدرجة الاقتصادية المميزة)",
    "home": "العودة", "Team": "فريق", "One Way": "ذهاب فقط",
}
LABEL_RE = re.compile(r"(?<!\w)(%s)(?!\w)" % "|".join(re.escape(w) for w in sorted(LABEL_WORDS, key=len, reverse=True)))

# ---------- counted words: 1, 2, 3-10, 11+ ----------
TRAVELLER = ("مسافر واحد", "مسافران", "مسافرين", "مسافراً")
ADULT = ("بالغ واحد", "بالغان", "بالغين", "بالغاً")
CHILD = ("طفل واحد", "طفلان", "أطفال", "طفلاً")
INFANT = ("رضيع واحد", "رضيعان", "رضّع", "رضيعاً")
STOP = ("توقف واحد", "توقفان", "توقفات", "توقفاً")
BAG = ("حقيبة مشحونة واحدة", "حقيبتان مشحونتان", "حقائب مشحونة", "حقيبة مشحونة")
SITE = ("موقع واحد", "موقعان", "مواقع", "موقعاً")
SIMILAR = ("خيار مشابه آخر", "خياران مشابهان آخران", "خيارات مشابهة أخرى", "خياراً مشابهاً آخر")
LEG = ("رحلة واحدة", "رحلتان", "رحلات", "رحلة")


def count(n, words):
    """3 -> '3 مسافرين', 1 -> 'مسافر واحد', 2 -> 'مسافران' (Arabic says one and two with the word alone)."""
    n = int(n)
    one, two, few, many = words
    return one if n == 1 else two if n == 2 else "%d %s" % (n, few if 3 <= n <= 10 else many)


def counted(words):  # a replacement for re.sub: the number in group 1, counted
    return lambda m: count(m[1], words)


def lead(m):  # "Every price is the total ... for all 4 travellers, in KWD."
    cur = "بالدينار الكويتي" if m[2] == "KWD" else "بعملة " + m[2]
    return "كل سعر هو إجمالي الرحلة كاملة (كل الرحلات، ذهاباً وعودة) لجميع المسافرين (%s)، %s." % (
        count(m[1], TRAVELLER), cur)


def sites_sell(m):
    n = int(m[1])
    return "%s %s هذه الرحلات" % (count(n, SITE), "يبيعان" if n == 2 else "تبيع")


LEGWORD = {"out": "رحلة الذهاب", "back": "رحلة العودة"}
VERB = {"leaves": "تغادر", "lands": "تصل", "has": "فيها"}


def leg_verb(m):  # "Out leaves" -> "رحلة الذهاب تغادر", "leg 2 has" -> "الرحلة 2 فيها"
    who = m[1].lower()
    who = LEGWORD.get(who) or "الرحلة " + who.split()[-1]
    return "%s %s" % (who, VERB[m[2]])


# ---------- 1. whole short nodes ----------
EXACT = {
    "Out": "ذهاب", "Back": "عودة", "One way": "ذهاب فقط", "Nonstop": "مباشرة بدون توقف", "Book": "احجز",
    "Economy": "الدرجة الاقتصادية", "Premium economy": "الدرجة الاقتصادية المميزة", "Premium": "الدرجة الاقتصادية المميزة",
    "Business": "درجة رجال الأعمال", "First": "الدرجة الأولى", "Airline": "شركة الطيران", "Whole trip": "الرحلة كاملة",
    "Cheapest site": "أرخص موقع", "Trip": "الرحلة", "Dates": "التواريخ", "no price": "لا يوجد سعر",
    "Top picks": "أفضل الاختيارات", "Best price per airline": "أفضل سعر لكل شركة طيران",
    "Whole-trip totals by date": "إجمالي الرحلة كاملة حسب التاريخ", "Every option, trip by trip": "كل الخيارات، رحلة رحلة",
    "Flight search · whole-trip prices": "بحث الرحلات · أسعار الرحلة كاملة", "flights on the site": "الرحلات على الموقع",
    "nothing found": "لم نجد شيئاً", "Airline not shown": "شركة الطيران غير معروضة", "round trip": "ذهاب وعودة",
    "one way": "ذهاب فقط", "multi-city": "وجهات متعددة", "Dark mode": "الوضع الداكن", "Light mode": "الوضع الفاتح",
    "Page options": "خيارات الصفحة",
    "Show where it stops": "اعرض أماكن التوقف", "Show flight details": "اعرض تفاصيل الرحلة",
    "Hide details": "إخفاء التفاصيل", "Sort by": "ترتيب حسب", "Fastest": "الأسرع", "Fewest stops": "أقل توقفات",
    "Leaves earliest": "الأبكر مغادرة", "Sort the tickets": "ترتيب التذاكر", "Stop": "التوقف", "Lands": "تهبط", "Leaves": "تقلع",
}

# ---------- 2. fixed sentences and pieces (plain text, in this order; case-sensitive) ----------
ORD = ["", "", "ثاني", "ثالث", "رابع", "خامس", "سادس", "سابع", "ثامن", "تاسع"]  # 2nd..9th for pick ranks
PHRASES = [
    ("Chosen from whole-trip prices: the cheapest, the best route (fewest stops, shortest flying), the best nonstop "
     "and the best on each airline you named. A tick marks each one a ticket wins; the next cheapest airlines fill up to "
     "three.", "اخترناها من أسعار الرحلة كاملة: الأرخص، وأفضل مسار (أقل توقفات وأقصر "
     "مدة طيران)، وأفضل رحلة مباشرة، والأفضل مع كل شركة طيران ذكرتها. علامة ✓ تبيّن ما تفوز به كل تذكرة، "
     "وتكمل أرخص شركات الطيران التالية العدد إلى ثلاث."),
    ("No nonstop found on this route", "لا توجد رحلة مباشرة على هذا المسار"),
    ("The airlines you named: each one's cheapest whole-trip price and the site that sells it.",
     "شركات الطيران التي ذكرتها: أرخص سعر للرحلة كاملة لكل منها، والموقع الذي يبيعه."),
    ("The cheapest price found on each airline (a mix of airlines counts under the one flying the longest flight); a "
     "note says what that option misses.", "أرخص سعر وجدناه لكل شركة طيران (الرحلة التي تجمع أكثر من شركة تُحسب للشركة "
     "التي تشغّل أطول رحلة فيها)؛ والملاحظة تذكر ما ينقص ذلك الخيار."),
    ("The cheapest normal ticket for each dates and route; tap a price to see its flights.",
     "أرخص تذكرة عادية لكل تواريخ ومسار؛ اضغط على السعر لرؤية رحلاته."),
    ("Each ticket: the flights out and back on a map, times, stops and waits, and every site that sells it.",
     "كل تذكرة: رحلات الذهاب والعودة على الخريطة، والأوقات والتوقفات ومدد الانتظار، وكل موقع يبيعها."),
    ("Prices change quickly. This page only searches; nothing was booked. Maps: Natural Earth, OurAirports. Logos: "
     "Google Flights.", "الأسعار تتغير بسرعة. هذه الصفحة تبحث فقط؛ لم يُحجز أي شيء. الخرائط: Natural Earth، OurAirports. "
     "الشعارات: Google Flights."),
    ("* Not a normal ticket (airport change, a hop between your trip's cities, a lower cabin on one flight, separate "
     "tickets, a converted price only, a Google round-trip price no other site confirmed, or an airline fare-calendar "
     "price without flights), or not what you asked for (nonstop, times, waits); kept out of the picks.",
     "* ليست تذكرة عادية (تغيير مطار، أو رحلة بين مدن رحلتك، أو درجة أقل في إحدى الرحلات، أو تذاكر منفصلة، أو سعر محوّل "
     "فقط، أو سعر ذهاب وعودة من Google لم يؤكده موقع آخر، أو سعر من تقويم أسعار شركة طيران بلا رحلات)، أو لا تطابق ما "
     "طلبت (رحلة مباشرة، الأوقات، مدد الانتظار)؛ لذلك لم تدخل ضمن الاختيارات."),
    ("Totals are for the whole trip and all travellers.", "الإجماليات للرحلة كاملة ولجميع المسافرين."),
    ("Check the final total on the airline or Google page before paying.",
     "تأكد من الإجمالي النهائي على صفحة شركة الطيران أو Google قبل الدفع."),
    ("(its Book button lists the airline/agency sellers)", "(زر الحجز فيه يعرض البائعين من شركات الطيران والوكالات)"),
    ("More airlines on Booking.com (cheapest each, flights on its page; some only fly a connecting flight): ",
     "شركات طيران أخرى على Booking.com (أرخص سعر لكل منها، والرحلات على صفحته؛ بعضها يشغّل رحلة ربط فقط): "),
    ("Cheaper on Google Flights (return flights not shown; confirm the total there): ",
     "أرخص على Google Flights (رحلات العودة غير معروضة؛ تأكد من الإجمالي هناك): "),
    ("return not shown; price not confirmed by another site", "رحلة العودة غير معروضة؛ لم يؤكد السعرَ موقعٌ آخر"),
    ("its own fare calendar shows this price for these dates; choose these flights on its site",
     "تقويم أسعارها يعرض هذا السعر لهذه التواريخ؛ اختر هذه الرحلات على موقعها"),
    ("may be missing from Almosafer's round-trip list; its one-way pages sell these flights",
     "قد لا تظهر في قائمة الذهاب والعودة في المسافر؛ صفحات الذهاب فقط فيه تبيع هذه الرحلات"),
    ("the airline's own lowest fare for these dates; pick the flights on its site",
     "أقل سعر لدى شركة الطيران نفسها لهذه التواريخ؛ اختر الرحلات على موقعها"),
    ("Flights not listed (the airline's own fare calendar)", "الرحلات غير مدرجة (من تقويم أسعار شركة الطيران نفسها)"),
    ("fare calendar price only: flights and each flight's cabin not shown; check on the airline's site",
     "سعر من تقويم الأسعار فقط: الرحلات ودرجة كل رحلة غير معروضة؛ تحقق على موقع شركة الطيران"),
    ("; choose them on its page.", "؛ اخترها على صفحته."),
    ("(other flight times, about the same price) on the site", "(أوقات رحلات أخرى، بنفس السعر تقريباً) على الموقع"),
    (", just after midnight: the night of ", "، بعد منتصف الليل بقليل: أي ليلة "),
    ("Whole trip, out and back", "الرحلة كاملة ذهاباً وعودة"),
    ("); the picks below don't: see each note.", ")؛ الاختيارات أدناه لا تطابقها: انظر ملاحظة كل منها."),
    ("Nothing found matches your wishes (", "لم نجد ما يطابق كل طلباتك ("),
    ('No price found (unknown, not "no flights").', "لم نجد سعراً (غير معروف، وليس «لا توجد رحلات»)."),
    ("No prices came back for ", "لم تصل أسعار لـ "),
    (', unknown, not "no flights": ', "، غير معروف، وليس «لا توجد رحلات»: "),
    ("prices only in another currency, not compared", "أسعار بعملة أخرى فقط، لم تُقارن"),
    ("Nothing searched: the plan had no trips.", "لم يتم البحث: الخطة بلا رحلات."),
    ("busy (rate-limited)", "مشغول (تجاوز حد الطلبات)"), ("timed out", "انتهت المهلة"),
    ("no flights listed", "لا توجد رحلات مدرجة"), ("not used for this trip type", "لا يُستخدم لهذا النوع من الرحلات"),
    ("source unavailable", "المصدر غير متاح"),
    ("No nonstop found in these results.", "لا توجد رحلة مباشرة في هذه النتائج."),
    ("Not in these results.", "غير موجودة في هذه النتائج."),
    ("): no ticket in these results has it on every leg.", "): لا توجد في هذه النتائج تذكرة تشملها في كل الرحلات."),
    ("Only part of the trip (", "جزء من الرحلة فقط ("),
    ("Not in the listed flights; Booking.com shows it from ", "ليست في الرحلات المعروضة؛ يعرضها Booking.com بدءاً من "),
    (" (may be only a connecting flight).", " (قد تكون رحلة ربط فقط)."),
    ("), not the long flight.", ")، وليس الرحلة الطويلة."),
    ("Cheapest with your bags confirmed: ", "الأرخص مع تأكيد حقائبك: "),
    ("; the options mix cabins.", "؛ الخيارات تجمع أكثر من درجة."),
    ("Budget airline: checked bags usually cost extra.", "شركة طيران اقتصادية: الحقائب المشحونة عادةً برسوم إضافية."),
    ("Airline on the Booking.com page", "شركة الطيران على صفحة Booking.com"),
    ("Nonstop, flights on the Booking.com link", "مباشرة، والرحلات على رابط Booking.com"),
    ("Closest options (each misses a wish):", "أقرب الخيارات (كل منها لا يطابق أحد طلباتك):"),
    ("a missed connection is your risk", "فوات رحلة الربط على مسؤوليتك"),
    ("check the total on the site", "تحقق من الإجمالي على الموقع"),
    ("not compared with the other prices", "لم يُقارن بالأسعار الأخرى"),
    ("Qatar prices in the origin country's currency", "أسعار القطرية بعملة بلد المغادرة"),
    ("results may be incomplete", "قد تكون النتائج ناقصة"),
]

# ---------- 4. ordered rules on what is left ----------
M = "|".join(MONTHS)
RULES = [
    # sentences with a number inside
    (r"Every price is the total for the whole trip \(every flight, out and back\) for all (\d+) travell?ers?, in (\w+)\.",
     lead),
    (r"Whole trip, all (\d+) legs", lambda m: "الرحلة كاملة، جميع الرحلات (%s)" % count(m[1], LEG)),
    (r"(\d+) sites sell these flights", sites_sell),
    (r"\+(\d+) similar options?", counted(SIMILAR)),
    (r"(\d+) one-way fares \(two bookings\)", "تذكرتا ذهاب فقط منفصلتان (حجزان)"),
    (r"(\d+) one-way fares", "تذكرتا ذهاب فقط منفصلتان"),
    (r"separate tickets \((\d+)\)", r"تذاكر منفصلة (\1)"),
    (r"Amadeus \(most airlines\) gave no answer in (\d+) s", r"Amadeus (أغلب شركات الطيران) لم يُجب خلال \1 ث"),
    (r"Feeder only: flies just the short connecting flights? \(",
     "رحلات ربط فقط: تشغّل رحلات الربط القصيرة فقط ("),
    (r"Flights not listed \((.+?)'s own fare calendar\); choose them on its site",
     r"الرحلات غير مدرجة (من تقويم أسعار \1 نفسها)؛ اخترها على موقعها"),
    (r"flights not shown by ", "الرحلات غير معروضة لدى "),
    # money: "KD 4,308" -> "4,308 د.ك"; another currency keeps its code after the number
    (r"\bKD (\d[\d,]*(?:\.\d+)?)", r"\1 د.ك"),
    (r"\b(USD|EUR|GBP|SAR|AED|QAR|BHD|OMR|JOD|EGP|TRY|INR|PKR|LKR|BDT|JPY|THB|MYR|SGD|AUD|CAD|CHF|CNY|KWD) "
     r"(\d[\d,]*(?:\.\d+)?)", r"\2 \1"),
    (r"converted price only \(≈ from (\w+)\)", r"سعر محوّل فقط (≈ من \1)"),
    (r"[Cc]onverted from ", "محوّل من "),
    (r"\(sold in SAR\)", "(يبيع بالريال السعودي)"),
    (r"\(sold in (\w+)\)", r"(يبيع بعملة \1)"),
    (r"priced in (\w+), not (\w+):", r"السعر بعملة \1 وليس \2:"),
    # wishes
    (r"(?i)doesn't match your wish: ", "لا يطابق طلبك: "),
    (r"(?i)fits your wishes: ", "يطابق طلباتك: "),
    (r" — misses: ", " — لا يطابق: "),
    (r"\(you asked nonstop\)", "(طلبت رحلة مباشرة)"),
    (r"\(you asked at most ([\d.]+) h\)", r"(طلبت \1 س كحد أقصى)"),
    (r"\(at most ([\d.]+) h\)", r"(\1 س كحد أقصى)"),
    (r"\(you asked waits of at most ([\d.]+) h\)", r"(طلبت انتظاراً لا يزيد عن \1 س)"),
    (r"\bwaits of at most ([\d.]+) h", r"انتظار لا يزيد عن \1 س"),
    (r"\(you need ", "(المطلوب: "),
    (r"\(you asked ", "(طلبت "),
    (r"(?i)\bflights not given\b", "الرحلات غير مذكورة"),
    (r"(?i)\btimes not given\b", "الأوقات غير مذكورة"),
    (r"(?i)\bbags not stated: check before booking", "الحقائب غير مذكورة: تحقق قبل الحجز"),
    (r"(?i)\blongest wait ", "أطول انتظار "),
    (r"\bno connections\b", "بدون رحلات ربط"),
    # waits and durations: "13h 15m wait" -> "انتظار 13 س 15 د"
    (r"(?i)\ba (-?\d+)h (\d+)m wait in ", r"انتظار \1 س \2 د في "),
    (r"(-?\d+)h (\d+)m wait", r"انتظار \1 س \2 د"),
    (r"(-?\d+)h (\d+)m flight", r"طيران \1 س \2 د"),
    (r"(-?\d+)h (\d+)m", r"\1 س \2 د"),
    # stops, travellers, bags
    (r"\bflights back not shown\b", "رحلات العودة غير معروضة"),
    (r"\bflights not shown\b", "الرحلات غير معروضة"),
    (r"(\d+) stops?\b", counted(STOP)),
    (r"(\d+) travell?ers?\b", counted(TRAVELLER)),
    (r"(\d+) adults?\b", counted(ADULT)),
    (r"(\d+) (?:child|children)\b", counted(CHILD)),
    (r"(\d+) infants?\b", counted(INFANT)),
    (r"\(age (\d+)\)", r"(العمر \1)"),
    (r"\(ages ([\d, ]+)\)", lambda m: "(الأعمار %s)" % m[1].replace(", ", "، ")),
    (r"(?i)\bcabin bag only\b", "حقيبة المقصورة فقط"),
    (r"(\d+(?:\.\d+)?) kg checked bag", r"حقيبة مشحونة \1 كغ"),
    (r"(\d+) checked bags?", counted(BAG)),
    (r"\b(?i:bags): ", "الحقائب: "),
    # leg words
    (r"\b([Oo]ut|[Bb]ack|[Ll]eg \d+) (leaves|lands|has)\b", leg_verb),
    (r"^Leaves\b", "الرحلة تغادر"), (r"\bhas\b", "فيها"),
    (r"\bleaves\b", "تغادر"), (r"\blands\b", "تصل"),
    (r"\bout (?=(?:after|before|by) \d)", "الذهاب "), (r"\bback (?=(?:after|before|by) \d)", "العودة "),
    (r"\bleg (\d+) (?=(?:after|before|by) \d)", r"الرحلة \1 "),
    (r"\bafter (?=\d)", "بعد "), (r"\bbefore (?=\d)", "قبل "), (r"\bby (?=\d)", "بحلول "),
    (r"\b[Oo]ut(?= (?:\d+ )?حق)", "الذهاب:"), (r"\bback(?= (?:\d+ )?حق)", "العودة:"), (r"\bleg (\d+):", r"الرحلة \1:"),
    (r"\(out\)", "(ذهاب)"), (r"\(back\)", "(عودة)"), (r"\(leg (\d+)\)", r"(الرحلة \1)"),
    (r"^Leg (\d+)$", r"الرحلة \1"),
    (r"^Stop (\d+)$", r"التوقف \1"),
    (r"^Airport change: ", "تغيير المطار: "),
    # pick labels, sellers, booking
    (r"\b[Cc]heapest at ", "الأرخص لدى "),
    (r" · cheapest\b", " · الأرخص"),
    *[(r"\b%d(?:st|nd|rd|th) cheapest airline\b" % n, "%s أرخص شركة طيران" % w) for n, w in enumerate(ORD) if w],
    *[(r"\b%d(?:st|nd|rd|th) best nonstop airline\b" % n, "%s أفضل شركة برحلة مباشرة" % w) for n, w in enumerate(ORD) if w],
    (r"\bNext cheapest\b", "الخيار الأرخص التالي"),
    (r"\bCheapest\b", "الأرخص"),
    (r"\bBest route\b", "أفضل مسار"),
    (r"\bBest nonstop\b", "أفضل رحلة مباشرة"),
    (r"\bBest on ", "الأفضل مع "),
    (r"\bnonstop\b", "رحلة مباشرة"), (r"\bNonstop\b", "مباشرة بدون توقف"),
    (r"\bSame price: ", "بنفس السعر: "),
    (r"\bBook on ", "احجز على "),
    (r"\(travel agency\)", "(وكالة سفر)"),
    (r"\(direct\)", "(مباشرة من الشركة)"),
    (r"\(sold as ", "(تُباع باسم "),
    (r" flown by ", " تشغّلها "),
    (r" via ", " عبر "),
    # the route of each leg
    (r"\bChange in ", "تغيير الطائرة في "),
    (r"; then ", "؛ ثم "),
    (r"(?<!Google )\bFlights\b", "الرحلات"),
    (r"\b[Nn]ote: ", "ملاحظة: "),
    (r"\bairport change ", "تغيير المطار "),
    (r"\bdomestic hop ", "رحلة داخلية "),
    (r"\bmixed cabin: (economy|premium|business|first) on ", lambda m: "درجات مختلفة: %s على " % CABINS[m[1]]),
    (r"(?i)\bnot (premium economy|economy|business class|first class) the whole way",
     lambda m: "ليست %s طوال الرحلة" % CABINS[m[1].lower()]),
    (r"\bNo (premium economy|economy|business class|first class) found for the whole trip on (the route |this route)",
     lambda m: "لم نجد %s للرحلة كاملة على %s" % (CABINS[m[1]], "هذا المسار" if m[2] == "this route" else "المسار ")),
    (r"\bin (\w+)'s own fare calendar", r"في تقويم أسعار \1"),
    # trips, labels, header
    (r"^(.+?) [Ii]n,? (.+?) [Oo]ut\b", r"الوصول إلى \1، والعودة من \2"),
    (r"\bInto ", "الوصول إلى "), (r", home from ", "، والعودة من "),
    (r"\bround trip\b", "ذهاب وعودة"), (r"\b[Oo]ne way\b", "ذهاب فقط"), (r"\bmulti-city\b", "وجهات متعددة"),
    (r"\bfamily trip\b", "رحلة عائلية"), (r"^Trip\b", "الرحلة"), (r"(\d+) legs\b", counted(LEG)),
    (r", at (?=\S)", "، لدى "), (r"\bto (?=[\u0600-\u06FF])", "إلى "),
    (LABEL_RE.pattern, lambda m: LABEL_WORDS[m[1]]),
    (r"^From ", "من "),
    (r"^Prices fetched ", "جُلبت الأسعار "),
    (r"(\d\d:\d\d) to (?=\d)", r"\1 إلى "),
    (r"^(.+) Fares$", r"أسعار \1"),
    (r"^Route map: ", "خريطة المسار: "),
    # dates: "Sat 19 Dec" -> "السبت 19 ديسمبر", "on Sat 19 Dec" -> "يوم السبت 19 ديسمبر"
    (r"\bon (?=(?:%s) \d)" % "|".join(WEEKDAYS), "يوم "),
    (r"\bon (?=\d{1,2} (?:%s)\b)" % M, "في "),
    (r"\b(%s)(?= \d)" % "|".join(WEEKDAYS), lambda m: WEEKDAYS[m[1]]),
    (r"(?<=\d )(%s)\b" % M, lambda m: MONTHS[m[1]]),
    (r"(?<=[\u0600-\u06FF] )(%s)\b" % M, lambda m: MONTHS[m[1]]),  # "late Nov" (أواخر Nov)
    (r"(?<=[\u0600-\u06FF]) or (?=[\u0600-\u06FF])", " أو "), (r"\bTrip$", "رحلة"),
]
RULES = [(re.compile(p), r) for p, r in RULES]
ARABIC = re.compile(r"[\u0600-\u06FF]")


def tidy(s):
    """Arabic commas after Arabic words, Arabic semicolons; "→" to "←" in Arabic text, unless Latin letters are on both sides
    ("(SYD → KUL)" stays: it reads left to right inside the Arabic line)."""
    if not ARABIC.search(s):
        return s
    s = re.sub(r"(?<=[\u0600-\u06FF)]),(?= |$)", "،", s)
    s = s.replace("; ", "؛ ")

    def arrow(m):
        left = re.findall(r"[A-Za-z\u0600-\u06FF]", s[:m.start()])
        right = re.findall(r"[A-Za-z\u0600-\u06FF]", s[m.end():])
        latin = left and right and left[-1].isascii() and right[0].isascii()
        return "→" if latin else "←"
    return re.sub("→", arrow, s)


def text(s):
    """One text (unescaped) in English -> Arabic; spaces around it are kept."""
    core = s.strip()
    if not core or not re.search(r"[A-Za-z]", core):
        return s
    pre, post = s[:len(s) - len(s.lstrip())], s[len(s.rstrip()):]
    if core in EXACT:
        return pre + EXACT[core] + post
    for en, ar in PHRASES:
        core = core.replace(en, ar)
    core = NAME_RE.sub(lambda m: NAMES[m[1]], core)
    for rx, rep in RULES:
        core = rx.sub(rep, core)
    return pre + tidy(core) + post


def attr(m):  # aria-label="..." (escaped with quotes)
    return 'aria-label="%s"' % escape(text(unescape(m[1])), quote=True)


def translate(html):
    """The page body in English -> the same HTML with its text in Arabic."""
    out = []
    for part in re.split(r"(<style\b.*?</style>|<script\b.*?</script>|<[^>]*>)", html, flags=re.S | re.I):
        if part.startswith("<"):
            if not re.match(r"<(style|script)\b", part, re.I):
                part = re.sub(r'aria-label="([^"]*)"', attr, part)
        elif part.strip():
            new = text(unescape(part))
            part = escape(new, quote=False) if new != unescape(part) else part
        out.append(part)
    return "".join(out)
