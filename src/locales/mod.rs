//! Compiled, static locale tables.
//!
//! All data lives in the binary as `&'static [&'static str]` arrays: there is zero runtime file
//! I/O. A small amount of derived data (ASCII-folded names used for e-mails and usernames) is
//! computed lazily, once per process, from those static tables.

use std::sync::OnceLock;

#[rustfmt::skip]
mod de_de;
#[rustfmt::skip]
mod en_gb;
#[rustfmt::skip]
mod en_us;
#[rustfmt::skip]
mod fr_fr;
#[rustfmt::skip]
mod ja_jp;

/// Ordering of given name and family name in a full name.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NameOrder {
    /// "John Smith"
    FirstLast,
    /// "佐藤 翔太"
    LastFirst,
}

/// Postal / addressing conventions for a locale.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AddressStyle {
    Us,
    Gb,
    De,
    Fr,
    Jp,
}

/// A compiled locale.
#[derive(Debug)]
pub struct Locale {
    pub code: &'static str,
    pub name_order: NameOrder,
    pub style: AddressStyle,
    pub first_names: &'static [&'static str],
    pub last_names: &'static [&'static str],
    /// Romanised given names (parallel to `first_names`) for non-Latin scripts.
    pub first_names_romanized: Option<&'static [&'static str]>,
    /// Romanised family names (parallel to `last_names`) for non-Latin scripts.
    pub last_names_romanized: Option<&'static [&'static str]>,
    pub cities: &'static [&'static str],
    pub states: &'static [&'static str],
    /// Parallel to `states` (empty when the locale has no customary abbreviations).
    pub state_abbrs: &'static [&'static str],
    pub street_names: &'static [&'static str],
    /// Street types/suffixes ("Street", "Road", "rue", ...). May be empty.
    pub street_suffixes: &'static [&'static str],
    /// Phone templates: `#` = 0-9, `%` = 1-9, `^` = 2-9; other characters are copied.
    pub phone_formats: &'static [&'static str],
    pub free_email_domains: &'static [&'static str],
    pub tlds: &'static [&'static str],
    /// Company templates: `{L}` = family name, `{S}` = suffix, `{W}` = company word.
    pub company_formats: &'static [&'static str],
    pub company_suffixes: &'static [&'static str],
    pub company_words: &'static [&'static str],
    pub job_titles: &'static [&'static str],
    pub words: &'static [&'static str],
    /// Separator between words in sentences ("" for Japanese).
    pub word_sep: &'static str,
    /// Sentence terminator ("." / "。").
    pub sentence_end: &'static str,
    /// Separator between sentences in a paragraph.
    pub sentence_sep: &'static str,
    /// Whether the first letter of a sentence is capitalised.
    pub capitalize: bool,
    pub derived: OnceLock<Derived>,
}

/// Lazily computed, locale-derived lookup tables.
#[derive(Debug)]
pub struct Derived {
    /// Lowercase ASCII given names for e-mails/usernames.
    pub first_ascii: Vec<String>,
    /// Lowercase ASCII family names for e-mails/usernames/domains.
    pub last_ascii: Vec<String>,
}

impl Locale {
    /// Lowercase ASCII-folded name tables (computed once per process).
    pub fn derived(&'static self) -> &'static Derived {
        self.derived.get_or_init(|| {
            let fold = |names: &[&str], romanized: Option<&[&str]>| -> Vec<String> {
                let src = romanized.unwrap_or(names);
                src.iter()
                    .map(|n| {
                        let s = ascii_fold(n);
                        if s.is_empty() {
                            "user".to_string()
                        } else {
                            s
                        }
                    })
                    .collect()
            };
            Derived {
                first_ascii: fold(self.first_names, self.first_names_romanized),
                last_ascii: fold(self.last_names, self.last_names_romanized),
            }
        })
    }
}

/// All built-in locales.
pub static LOCALES: [&Locale; 5] = [
    &en_us::EN_US,
    &en_gb::EN_GB,
    &de_de::DE_DE,
    &fr_fr::FR_FR,
    &ja_jp::JA_JP,
];

/// Look up a locale by code. Accepts `en_US`, `en-US`, `en_us`, ... and the bare language
/// codes `en`, `de`, `fr`, `ja`.
pub fn get(code: &str) -> Option<&'static Locale> {
    let norm: String = code
        .trim()
        .chars()
        .map(|c| {
            if c == '-' {
                '_'
            } else {
                c.to_ascii_lowercase()
            }
        })
        .collect();
    let norm = match norm.as_str() {
        "en" => "en_us",
        "de" => "de_de",
        "fr" => "fr_fr",
        "ja" | "jp" => "ja_jp",
        "en_uk" => "en_gb",
        other => other,
    };
    LOCALES
        .iter()
        .copied()
        .find(|l| l.code.eq_ignore_ascii_case(norm))
}

/// Real UK postcode areas.
pub fn gb_postcode_areas() -> &'static [&'static str] {
    en_gb::POSTCODE_AREAS
}

/// Codes of all built-in locales.
pub fn codes() -> Vec<&'static str> {
    LOCALES.iter().map(|l| l.code).collect()
}

/// Fold a (possibly accented) Latin name into lowercase ASCII `[a-z0-9]`.
pub fn ascii_fold(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for ch in s.chars().flat_map(char::to_lowercase) {
        let rep: &str = match ch {
            'a'..='z' | '0'..='9' => {
                out.push(ch);
                continue;
            }
            'ä' | 'æ' => "ae",
            'ö' | 'œ' | 'ø' => "oe",
            'ü' => "ue",
            'ß' => "ss",
            'à' | 'á' | 'â' | 'ã' | 'å' | 'ā' | 'ą' => "a",
            'ç' | 'ć' | 'č' => "c",
            'è' | 'é' | 'ê' | 'ë' | 'ē' | 'ę' | 'ě' => "e",
            'ì' | 'í' | 'î' | 'ï' | 'ı' | 'ī' => "i",
            'ñ' | 'ń' | 'ň' => "n",
            'ò' | 'ó' | 'ô' | 'õ' | 'ō' => "o",
            'ù' | 'ú' | 'û' | 'ū' | 'ů' => "u",
            'ý' | 'ÿ' => "y",
            'ş' | 'ś' | 'š' => "s",
            'ğ' => "g",
            'ł' => "l",
            'ź' | 'ż' | 'ž' => "z",
            'ř' => "r",
            'đ' | 'ď' => "d",
            'ť' => "t",
            _ => "",
        };
        out.push_str(rep);
    }
    out
}

// ---------------------------------------------------------------------------------------------
// Locale-independent tables
// ---------------------------------------------------------------------------------------------

/// Country names (English), parallel to [`COUNTRY_CODES`].
#[rustfmt::skip]
pub static COUNTRIES: &[&str] = &[
    "United States", "United Kingdom", "Germany", "France", "Japan", "Canada", "Australia",
    "Brazil", "India", "China", "Mexico", "Spain", "Italy", "Netherlands", "Sweden", "Norway",
    "Denmark", "Finland", "Poland", "Switzerland", "Austria", "Belgium", "Ireland", "Portugal",
    "Greece", "Turkey", "Ukraine", "South Korea", "Singapore", "New Zealand", "South Africa",
    "Nigeria", "Kenya", "Egypt", "Morocco", "Argentina", "Chile", "Colombia", "Peru", "Indonesia",
    "Malaysia", "Thailand", "Vietnam", "Philippines", "Pakistan", "Bangladesh", "Saudi Arabia",
    "United Arab Emirates", "Israel", "Czechia", "Hungary", "Romania", "Iceland", "Luxembourg",
    "Estonia", "Croatia", "Slovenia", "Taiwan", "Ghana", "Uruguay",
];

/// ISO 3166-1 alpha-2 codes, parallel to [`COUNTRIES`].
#[rustfmt::skip]
pub static COUNTRY_CODES: &[&str] = &[
    "US", "GB", "DE", "FR", "JP", "CA", "AU", "BR", "IN", "CN", "MX", "ES", "IT", "NL", "SE", "NO",
    "DK", "FI", "PL", "CH", "AT", "BE", "IE", "PT", "GR", "TR", "UA", "KR", "SG", "NZ", "ZA", "NG",
    "KE", "EG", "MA", "AR", "CL", "CO", "PE", "ID", "MY", "TH", "VN", "PH", "PK", "BD", "SA", "AE",
    "IL", "CZ", "HU", "RO", "IS", "LU", "EE", "HR", "SI", "TW", "GH", "UY",
];

/// ISO 4217 currency codes.
#[rustfmt::skip]
pub static CURRENCY_CODES: &[&str] = &[
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY", "INR", "BRL", "MXN", "SEK", "NOK",
    "DKK", "PLN", "KRW", "SGD", "NZD", "ZAR", "HKD", "TRY", "AED", "SAR", "THB", "IDR", "CZK",
    "HUF", "ILS",
];

/// User-agent templates. Tokens: `{CH}` Chrome major, `{FF}` Firefox major, `{SF}` Safari major,
/// `{IOS}` iOS major, `{AND}` Android major, `{PX}` Pixel model, `{N}` minor version digit.
#[rustfmt::skip]
pub static USER_AGENTS: &[&str] = &[
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{CH}.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{CH}.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{CH}.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{CH}.0.0.0 Safari/537.36 Edg/{CH}.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{FF}.0) Gecko/20100101 Firefox/{FF}.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:{FF}.0) Gecko/20100101 Firefox/{FF}.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:{FF}.0) Gecko/20100101 Firefox/{FF}.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{SF}.{N} Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS {IOS}_{N} like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{IOS}.{N} Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS {IOS}_{N} like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{IOS}.{N} Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android {AND}; Pixel {PX}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{CH}.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android {AND}; SM-S91{N}B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{CH}.0.0.0 Mobile Safari/537.36",
];

/// English job titles shared by the English-language locales.
#[rustfmt::skip]
pub static JOB_TITLES_EN: &[&str] = &[
    "Software Engineer", "Data Scientist", "Product Manager", "Project Manager", "Accountant",
    "Registered Nurse", "Teacher", "Marketing Manager", "Sales Representative", "Graphic Designer",
    "Civil Engineer", "Mechanical Engineer", "Financial Analyst", "Human Resources Manager",
    "Operations Manager", "Customer Service Representative", "Administrative Assistant",
    "Web Developer", "Systems Administrator", "Database Administrator", "Business Analyst",
    "Management Consultant", "Lawyer", "Paralegal", "Pharmacist", "Physician", "Dentist",
    "Physical Therapist", "Electrician", "Plumber", "Architect", "Chef", "Journalist", "Editor",
    "Copywriter", "UX Designer", "DevOps Engineer", "Security Analyst", "Network Engineer",
    "Research Scientist", "Laboratory Technician", "Veterinarian", "Airline Pilot",
    "Police Officer", "Firefighter", "Real Estate Agent", "Insurance Underwriter", "Loan Officer",
    "Auditor", "Chief Executive Officer", "Chief Technology Officer", "Chief Financial Officer",
    "Supply Chain Manager", "Logistics Coordinator", "Social Worker", "Psychologist", "Librarian",
    "Photographer", "Interior Designer", "Machine Learning Engineer", "Quality Assurance Engineer",
    "Technical Writer", "Site Reliability Engineer", "Account Executive", "Office Manager",
];

/// English words for sentences, paragraphs, domains and URL paths.
#[rustfmt::skip]
pub static WORDS_EN: &[&str] = &[
    "time", "year", "people", "way", "day", "man", "thing", "woman", "life", "child", "world",
    "school", "state", "family", "student", "group", "country", "problem", "hand", "part", "place",
    "case", "week", "company", "system", "program", "question", "work", "government", "number",
    "night", "point", "home", "water", "room", "mother", "area", "money", "story", "fact", "month",
    "lot", "right", "study", "book", "eye", "job", "word", "business", "issue", "side", "kind",
    "head", "house", "service", "friend", "father", "power", "hour", "game", "line", "end",
    "member", "law", "car", "city", "community", "name", "president", "team", "minute", "idea",
    "kid", "body", "information", "back", "parent", "face", "others", "level", "office", "door",
    "health", "person", "art", "war", "history", "party", "result", "change", "morning", "reason",
    "research", "girl", "guy", "moment", "air", "teacher", "force", "education", "foot", "boy",
    "age", "policy", "music", "market", "sense", "nation", "plan", "college", "interest", "death",
    "experience", "effect", "class", "control", "care", "field", "development", "role", "effort",
    "rate", "heart", "drug", "show", "leader", "light", "voice", "wife", "police", "mind", "price",
    "report", "decision", "son", "view", "relationship", "town", "road", "arm", "difference",
    "value", "building", "action", "model", "season", "society", "tax", "director", "position",
    "player", "record", "paper", "space", "ground", "form", "event", "official", "matter", "center",
    "couple", "site", "project", "activity", "star", "table", "need", "court", "oil", "situation",
    "cost", "industry", "figure", "street", "image", "phone", "data", "picture", "practice",
    "piece", "land", "product", "doctor", "wall", "patient", "worker", "news", "test", "movie",
    "north", "love", "support", "technology", "step", "baby", "computer", "type", "attention",
    "film", "tree", "source", "organization", "hair", "window", "evidence", "population", "signal",
    "energy", "garden", "river", "summer", "winter", "coffee", "travel", "simple", "modern",
    "quick", "happy", "bright", "green", "open", "early", "local", "strong", "clear", "small",
    "large",
];

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn locale_lookup() {
        assert_eq!(get("en_US").unwrap().code, "en_US");
        assert_eq!(get("en-gb").unwrap().code, "en_GB");
        assert_eq!(get("DE_de").unwrap().code, "de_DE");
        assert_eq!(get("ja").unwrap().code, "ja_JP");
        assert!(get("xx_XX").is_none());
    }

    #[test]
    fn parallel_tables_are_consistent() {
        assert_eq!(COUNTRIES.len(), COUNTRY_CODES.len());
        for loc in LOCALES {
            assert!(!loc.first_names.is_empty(), "{}", loc.code);
            assert!(!loc.last_names.is_empty(), "{}", loc.code);
            assert!(!loc.cities.is_empty(), "{}", loc.code);
            assert!(!loc.states.is_empty(), "{}", loc.code);
            assert!(!loc.phone_formats.is_empty(), "{}", loc.code);
            assert!(!loc.company_formats.is_empty(), "{}", loc.code);
            assert!(!loc.words.is_empty(), "{}", loc.code);
            assert!(!loc.free_email_domains.is_empty(), "{}", loc.code);
            assert!(!loc.tlds.is_empty(), "{}", loc.code);
            assert!(!loc.job_titles.is_empty(), "{}", loc.code);
            assert!(!loc.street_names.is_empty(), "{}", loc.code);
            if !loc.state_abbrs.is_empty() {
                assert_eq!(loc.states.len(), loc.state_abbrs.len(), "{}", loc.code);
            }
            if let Some(r) = loc.first_names_romanized {
                assert_eq!(r.len(), loc.first_names.len(), "{}", loc.code);
            }
            if let Some(r) = loc.last_names_romanized {
                assert_eq!(r.len(), loc.last_names.len(), "{}", loc.code);
            }
            let d = loc.derived();
            assert!(d.first_ascii.iter().all(|s| !s.is_empty()
                && s.bytes()
                    .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit())));
            assert!(d.last_ascii.iter().all(|s| !s.is_empty()
                && s.bytes()
                    .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit())));
        }
    }

    #[test]
    fn folding() {
        assert_eq!(ascii_fold("Müller"), "mueller");
        assert_eq!(ascii_fold("Lefèvre"), "lefevre");
        assert_eq!(ascii_fold("O'Brien"), "obrien");
        assert_eq!(ascii_fold("Le Gall"), "legall");
        assert_eq!(ascii_fold("Großmann"), "grossmann");
        assert_eq!(ascii_fold("Éloïse"), "eloise");
    }
}
