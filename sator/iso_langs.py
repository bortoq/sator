#!/usr/bin/env python3
"""ISO 639 language database and lookup functions."""

import re
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# ISO 639 LANGUAGE DATABASE
# ═══════════════════════════════════════════════════════════════════════════════
# fmt: off
ISO_LANGUAGES = [
    ("aa", "aar", "aar", "aar", "Afar", "Afar", "Q29321"),
    ("ab", "abk", "abk", "abk", "Abkhazian", "Аҧсуа", "Q5111"),
    ("ae", "ave", "ave", "ave", "Avestan", "Avesta", "Q29572"),
    ("af", "afr", "afr", "afr", "Afrikaans", "Afrikaans", "Q14196"),
    ("ak", "aka", "aka", "aka", "Akan", "Akan", "Q28026"),
    ("am", "amh", "amh", "amh", "Amharic", "አማርኛ", "Q28244"),
    ("an", "arg", "arg", "arg", "Aragonese", "Aragonés", "Q8765"),
    ("ar", "ara", "ara", "ara", "Arabic", "العربية", "Q13955"),
    ("as", "asm", "asm", "asm", "Assamese", "অসমীয়া", "Q29401"),
    ("av", "ava", "ava", "ava", "Avaric", "Авар", "Q29561"),
    ("ay", "aym", "aym", "aym", "Aymara", "Aymar", "Q4627"),
    ("az", "aze", "aze", "aze", "Azerbaijani", "Azərbaycan", "Q9292"),
    ("ba", "bak", "bak", "bak", "Bashkir", "Башҡорт", "Q33065"),
    ("be", "bel", "bel", "bel", "Belarusian", "Беларуская", "Q9091"),
    ("bg", "bul", "bul", "bul", "Bulgarian", "Български", "Q7918"),
    ("bh", "bih", "bih", "bih", "Bihari", "भोजपुरी", "Q33268"),
    ("bi", "bis", "bis", "bis", "Bislama", "Bislama", "Q35452"),
    ("bm", "bam", "bam", "bam", "Bambara", "Bamanankan", "Q33243"),
    ("bn", "ben", "ben", "ben", "Bengali", "বাংলা", "Q9610"),
    ("bo", "tib", "bod", "bod", "Tibetan", "བོད་ཡིག", "Q34271"),
    ("br", "bre", "bre", "bre", "Breton", "Brezhoneg", "Q12107"),
    ("bs", "bos", "bos", "bos", "Bosnian", "Bosanski", "Q9303"),
    ("ca", "cat", "cat", "cat", "Catalan", "Català", "Q7026"),
    ("ce", "che", "che", "che", "Chechen", "Нохчийн", "Q33350"),
    ("ch", "cha", "cha", "cha", "Chamorro", "Chamoru", "Q33262"),
    ("co", "cos", "cos", "cos", "Corsican", "Corsu", "Q33285"),
    ("cr", "cre", "cre", "cre", "Cree", "ᓀᐦᐃᔭᐍᐏᐣ", "Q33372"),
    ("cs", "cze", "ces", "ces", "Czech", "Čeština", "Q9056"),
    ("cu", "chu", "chu", "chu", "Church Slavic", "Ѩзыкъ словѣньскъ", "Q35499"),
    ("cv", "chv", "chv", "chv", "Chuvash", "Чӑваш", "Q33346"),
    ("cy", "wel", "cym", "cym", "Welsh", "Cymraeg", "Q9309"),
    ("da", "dan", "dan", "dan", "Danish", "Dansk", "Q9035"),
    ("de", "ger", "deu", "deu", "German", "Deutsch", "Q188"),
    ("dv", "div", "div", "div", "Divehi", "ދިވެހި", "Q32656"),
    ("dz", "dzo", "dzo", "dzo", "Dzongkha", "རྫོང་ཁ", "Q33276"),
    ("ee", "ewe", "ewe", "ewe", "Ewe", "Eʋegbe", "Q33278"),
    ("el", "gre", "ell", "ell", "Greek", "Ελληνικά", "Q9129"),
    ("en", "eng", "eng", "eng", "English", "English", "Q1860"),
    ("eo", "epo", "epo", "epo", "Esperanto", "Esperanto", "Q143"),
    ("es", "spa", "spa", "spa", "Spanish", "Español", "Q1321"),
    ("et", "est", "est", "est", "Estonian", "Eesti", "Q9072"),
    ("eu", "baq", "eus", "eus", "Basque", "Euskara", "Q8752"),
    ("fa", "per", "fas", "fas", "Persian", "فارسی", "Q9168"),
    ("ff", "ful", "ful", "ful", "Fulah", "Fulfulde", "Q33298"),
    ("fi", "fin", "fin", "fin", "Finnish", "Suomi", "Q1412"),
    ("fj", "fij", "fij", "fij", "Fijian", "Na Vosa Vakaviti", "Q33295"),
    ("fo", "fao", "fao", "fao", "Faroese", "Føroyskt", "Q25228"),
    ("fr", "fre", "fra", "fra", "French", "Français", "Q150"),
    ("fy", "fry", "fry", "fry", "Western Frisian", "Frysk", "Q27175"),
    ("ga", "gle", "gle", "gle", "Irish", "Gaeilge", "Q9142"),
    ("gd", "gla", "gla", "gla", "Scottish Gaelic", "Gàidhlig", "Q9314"),
    ("gl", "glg", "glg", "glg", "Galician", "Galego", "Q10134"),
    ("gn", "grn", "grn", "grn", "Guarani", "Avañe'ẽ", "Q35876"),
    ("gu", "guj", "guj", "guj", "Gujarati", "ગુજરાતી", "Q5137"),
    ("gv", "glv", "glv", "glv", "Manx", "Gaelg", "Q12175"),
    ("ha", "hau", "hau", "hau", "Hausa", "Hausa", "Q56475"),
    ("he", "heb", "heb", "heb", "Hebrew", "עברית", "Q9288"),
    ("hi", "hin", "hin", "hin", "Hindi", "हिन्दी", "Q1568"),
    ("ho", "hmo", "hmo", "hmo", "Hiri Motu", "Hiri Motu", "Q33558"),
    ("hr", "hrv", "hrv", "hrv", "Croatian", "Hrvatski", "Q6654"),
    ("ht", "hat", "hat", "hat", "Haitian", "Kreyòl ayisyen", "Q33473"),
    ("hu", "hun", "hun", "hun", "Hungarian", "Magyar", "Q9067"),
    ("hy", "arm", "hye", "hye", "Armenian", "Հայերեն", "Q8785"),
    ("hz", "her", "her", "her", "Herero", "Otjiherero", "Q33491"),
    ("ia", "ina", "ina", "ina", "Interlingua", "Interlingua", "Q35939"),
    ("id", "ind", "ind", "ind", "Indonesian", "Bahasa Indonesia", "Q9240"),
    ("ie", "ile", "ile", "ile", "Interlingue", "Interlingue", "Q35852"),
    ("ig", "ibo", "ibo", "ibo", "Igbo", "Igbo", "Q33578"),
    ("ii", "iii", "iii", "iii", "Sichuan Yi", "ꆈꌠ꒿", "Q33701"),
    ("ik", "ipk", "ipk", "ipk", "Inupiaq", "Iñupiatun", "Q33583"),
    ("io", "ido", "ido", "ido", "Ido", "Ido", "Q352"),
    ("is", "ice", "isl", "isl", "Icelandic", "Íslenska", "Q294"),
    ("it", "ita", "ita", "ita", "Italian", "Italiano", "Q652"),
    ("iu", "iku", "iku", "iku", "Inuktitut", "ᐃᓄᒃᑎᑐᑦ", "Q29921"),
    ("ja", "jpn", "jpn", "jpn", "Japanese", "日本語", "Q5287"),
    ("jv", "jav", "jav", "jav", "Javanese", "Basa Jawa", "Q33349"),
    ("ka", "geo", "kat", "kat", "Georgian", "ქართული", "Q8108"),
    ("kg", "kon", "kon", "kon", "Kongo", "Kikongo", "Q33702"),
    ("ki", "kik", "kik", "kik", "Kikuyu", "Gĩkũyũ", "Q33587"),
    ("kj", "kua", "kua", "kua", "Kuanyama", "Kuanyama", "Q33592"),
    ("kk", "kaz", "kaz", "kaz", "Kazakh", "Қазақша", "Q9252"),
    ("kl", "kal", "kal", "kal", "Kalaallisut", "Kalaallisut", "Q33595"),
    ("km", "khm", "khm", "khm", "Khmer", "ភាសាខ្មែរ", "Q9205"),
    ("kn", "kan", "kan", "kan", "Kannada", "ಕನ್ನಡ", "Q33673"),
    ("ko", "kor", "kor", "kor", "Korean", "한국어", "Q9176"),
    ("kr", "kau", "kau", "kau", "Kanuri", "Kanuri", "Q33697"),
    ("ks", "kas", "kas", "kas", "Kashmiri", "कॉशुर", "Q33531"),
    ("ku", "kur", "kur", "kur", "Kurdish", "Kurdî", "Q36163"),
    ("kv", "kom", "kom", "kom", "Komi", "Коми", "Q33707"),
    ("kw", "cor", "cor", "cor", "Cornish", "Kernowek", "Q25289"),
    ("ky", "kir", "kir", "kir", "Kyrgyz", "Кыргызча", "Q9255"),
    ("la", "lat", "lat", "lat", "Latin", "Latina", "Q397"),
    ("lb", "ltz", "ltz", "ltz", "Luxembourgish", "Lëtzebuergesch", "Q9051"),
    ("lg", "lug", "lug", "lug", "Ganda", "Luganda", "Q33368"),
    ("li", "lim", "lim", "lim", "Limburgish", "Limburgs", "Q102172"),
    ("ln", "lin", "lin", "lin", "Lingala", "Lingála", "Q36217"),
    ("lo", "lao", "lao", "lao", "Lao", "ລາວ", "Q9211"),
    ("lt", "lit", "lit", "lit", "Lithuanian", "Lietuvių", "Q9083"),
    ("lu", "lub", "lub", "lub", "Luba-Katanga", "Kiluba", "Q36224"),
    ("lv", "lav", "lav", "lav", "Latvian", "Latviešu", "Q9052"),
    ("mg", "mlg", "mlg", "mlg", "Malagasy", "Malagasy", "Q36270"),
    ("mh", "mah", "mah", "mah", "Marshallese", "Kajin M̧ajeļ", "Q36276"),
    ("mi", "mao", "mri", "mri", "Maori", "Te Reo Māori", "Q36451"),
    ("mk", "mac", "mkd", "mkd", "Macedonian", "Македонски", "Q9296"),
    ("ml", "mal", "mal", "mal", "Malayalam", "മലയാളം", "Q36236"),
    ("mn", "mon", "mon", "mon", "Mongolian", "Монгол", "Q9246"),
    ("mr", "mar", "mar", "mar", "Marathi", "मराठी", "Q1571"),
    ("ms", "may", "msa", "msa", "Malay", "Bahasa Melayu", "Q9237"),
    ("mt", "mlt", "mlt", "mlt", "Maltese", "Malti", "Q9166"),
    ("my", "bur", "mya", "mya", "Burmese", "မြန်မာဘာသာ", "Q9228"),
    ("na", "nau", "nau", "nau", "Nauru", "Dorerin Naoero", "Q13307"),
    ("nb", "nob", "nob", "nob", "Norwegian Bokmål", "Norsk bokmål", "Q25167"),
    ("nd", "nde", "nde", "nde", "North Ndebele", "IsiNdebele", "Q36739"),
    ("ne", "nep", "nep", "nep", "Nepali", "नेपाली", "Q33823"),
    ("ng", "ndo", "ndo", "ndo", "Ndonga", "Oshiwambo", "Q36746"),
    ("nl", "dut", "nld", "nld", "Dutch", "Nederlands", "Q7411"),
    ("nn", "nno", "nno", "nno", "Norwegian Nynorsk", "Norsk nynorsk", "Q25164"),
    ("no", "nor", "nor", "nor", "Norwegian", "Norsk", "Q9043"),
    ("nr", "nbl", "nbl", "nbl", "South Ndebele", "IsiNdebele", "Q36735"),
    ("nv", "nav", "nav", "nav", "Navajo", "Diné bizaad", "Q13310"),
    ("ny", "nya", "nya", "nya", "Chichewa", "ChiCheŵa", "Q33273"),
    ("oc", "oci", "oci", "oci", "Occitan", "Occitan", "Q14185"),
    ("oj", "oji", "oji", "oji", "Ojibwa", "ᐊᓂᔑᓈᐯᒧᐎᓐ", "Q33875"),
    ("om", "orm", "orm", "orm", "Oromo", "Afaan Oromoo", "Q33864"),
    ("or", "ori", "ori", "ori", "Odia", "ଓଡ଼ିଆ", "Q33810"),
    ("os", "oss", "oss", "oss", "Ossetian", "Ирон", "Q33968"),
    ("pa", "pan", "pan", "pan", "Punjabi", "ਪੰਜਾਬੀ", "Q58635"),
    ("pi", "pli", "pli", "pli", "Pali", "पालि", "Q36727"),
    ("pl", "pol", "pol", "pol", "Polish", "Polski", "Q809"),
    ("ps", "pus", "pus", "pus", "Pashto", "پښتو", "Q58680"),
    ("pt", "por", "por", "por", "Portuguese", "Português", "Q5146"),
    ("qu", "que", "que", "que", "Quechua", "Runa Simi", "Q7738"),
    ("rm", "roh", "roh", "roh", "Romansh", "Rumantsch", "Q13199"),
    ("rn", "run", "run", "run", "Rundi", "Ikirundi", "Q33541"),
    ("ro", "rum", "ron", "ron", "Romanian", "Română", "Q7913"),
    ("ru", "rus", "rus", "rus", "Russian", "Русский", "Q7737"),
    ("rw", "kin", "kin", "kin", "Kinyarwanda", "Ikinyarwanda", "Q33541"),
    ("sa", "san", "san", "san", "Sanskrit", "संस्कृतम्", "Q11059"),
    ("sc", "srd", "srd", "srd", "Sardinian", "Sardu", "Q33976"),
    ("sd", "snd", "snd", "snd", "Sindhi", "سنڌي", "Q33997"),
    ("se", "sme", "sme", "sme", "Northern Sami", "Sámegiella", "Q33986"),
    ("sg", "sag", "sag", "sag", "Sango", "Sängö", "Q33954"),
    ("sh", "scr", "hbs", "hbs", "Serbo-Croatian", "Srpskohrvatski", "Q9301"),
    ("si", "sin", "sin", "sin", "Sinhala", "සිංහල", "Q13267"),
    ("sk", "slo", "slk", "slk", "Slovak", "Slovenčina", "Q9058"),
    ("sl", "slv", "slv", "slv", "Slovenian", "Slovenščina", "Q9063"),
    ("sm", "smo", "smo", "smo", "Samoan", "Gagana Samoa", "Q34011"),
    ("sn", "sna", "sna", "sna", "Shona", "ChiShona", "Q34004"),
    ("so", "som", "som", "som", "Somali", "Soomaali", "Q13275"),
    ("sq", "alb", "sqi", "sqi", "Albanian", "Shqip", "Q8748"),
    ("sr", "srp", "srp", "srp", "Serbian", "Српски", "Q9299"),
    ("ss", "ssw", "ssw", "ssw", "Swati", "SiSwati", "Q34059"),
    ("st", "sot", "sot", "sot", "Southern Sotho", "Sesotho", "Q34340"),
    ("su", "sun", "sun", "sun", "Sundanese", "Basa Sunda", "Q34002"),
    ("sv", "swe", "swe", "swe", "Swedish", "Svenska", "Q9027"),
    ("sw", "swa", "swa", "swa", "Swahili", "Kiswahili", "Q7838"),
    ("ta", "tam", "tam", "tam", "Tamil", "தமிழ்", "Q5885"),
    ("te", "tel", "tel", "tel", "Telugu", "తెలుగు", "Q8097"),
    ("tg", "tgk", "tgk", "tgk", "Tajik", "Тоҷикӣ", "Q9260"),
    ("th", "tha", "tha", "tha", "Thai", "ไทย", "Q9217"),
    ("ti", "tir", "tir", "tir", "Tigrinya", "ትግርኛ", "Q34124"),
    ("tk", "tuk", "tuk", "tuk", "Turkmen", "Türkmençe", "Q9267"),
    ("tl", "tgl", "tgl", "tgl", "Tagalog", "Tagalog", "Q34057"),
    ("tn", "tsn", "tsn", "tsn", "Tswana", "Setswana", "Q34137"),
    ("to", "ton", "ton", "ton", "Tongan", "Lea faka-Tonga", "Q34094"),
    ("tr", "tur", "tur", "tur", "Turkish", "Türkçe", "Q256"),
    ("ts", "tso", "tso", "tso", "Tsonga", "Xitsonga", "Q34327"),
    ("tt", "tat", "tat", "tat", "Tatar", "Татарча", "Q9264"),
    ("tw", "twi", "twi", "twi", "Twi", "Twi", "Q34154"),
    ("ty", "tah", "tah", "tah", "Tahitian", "Reo Tahiti", "Q34128"),
    ("ug", "uig", "uig", "uig", "Uyghur", "ئۇيغۇرچە", "Q9247"),
    ("uk", "ukr", "ukr", "ukr", "Ukrainian", "Українська", "Q8798"),
    ("ur", "urd", "urd", "urd", "Urdu", "اردو", "Q1617"),
    ("uz", "uzb", "uzb", "uzb", "Uzbek", "Oʻzbek", "Q9264"),
    ("ve", "ven", "ven", "ven", "Venda", "Tshivenḓa", "Q34173"),
    ("vi", "vie", "vie", "vie", "Vietnamese", "Tiếng Việt", "Q9199"),
    ("vo", "vol", "vol", "vol", "Volapük", "Volapük", "Q36986"),
    ("wa", "wln", "wln", "wln", "Walloon", "Walon", "Q34219"),
    ("wo", "wol", "wol", "wol", "Wolof", "Wolof", "Q34257"),
    ("xh", "xho", "xho", "xho", "Xhosa", "IsiXhosa", "Q13218"),
    ("yi", "yid", "yid", "yid", "Yiddish", "ייִדיש", "Q8641"),
    ("yo", "yor", "yor", "yor", "Yoruba", "Yorùbá", "Q34311"),
    ("za", "zha", "zha", "zha", "Zhuang", "Vahcuengh", "Q34360"),
    ("zh", "chi", "zho", "zho", "Chinese", "中文", "Q7855"),
    ("zu", "zul", "zul", "zul", "Zulu", "IsiZulu", "Q10179"),
]
# fmt: on

# Build lookup dicts
_ISO_BY_1 = {}
_ISO_BY_3 = {}
_ISO_BY_NAME = {}
for entry in ISO_LANGUAGES:
    _ISO_BY_1[entry[0]] = entry
    _ISO_BY_3[entry[1]] = entry
    _ISO_BY_3[entry[2]] = entry
    _ISO_BY_3[entry[3]] = entry
    _ISO_BY_NAME[entry[4].lower()] = entry
    _ISO_BY_NAME[entry[5].lower()] = entry

def iso_lookup(key: str) -> Optional[dict]:
    """Look up a language by ISO 639-1 code, ISO 639-3 code, or English/native name."""
    key = key.strip().lower()
    if len(key) == 2:
        entry = _ISO_BY_1.get(key)
    elif len(key) == 3:
        entry = _ISO_BY_3.get(key)
    else:
        entry = _ISO_BY_NAME.get(key)
    if entry:
        return {
            "iso_639_1": entry[0],
            "iso_639_2b": entry[1],
            "iso_639_2t": entry[2],
            "iso_639_3": entry[3],
            "name_en": entry[4],
            "name_native": entry[5],
            "wikidata_q": entry[6],
        }
    return None

def iso_name(code: str) -> str:
    """Get English name for ISO 639-1 code."""
    entry = _ISO_BY_1.get(code.lower())
    return entry[4] if entry else code

def iso_code(name: str) -> str:
    """Get ISO 639-1 code from English or native name."""
    entry = _ISO_BY_NAME.get(name.lower().strip())
    if entry:
        return entry[0]
    # Try matching substring
    for e in ISO_LANGUAGES:
        if name.lower() in e[4].lower() or name.lower() in e[5].lower():
            return e[0]
    return ""

