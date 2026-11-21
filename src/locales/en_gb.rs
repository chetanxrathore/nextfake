//! English (United Kingdom).

use super::{AddressStyle, Locale, NameOrder, JOB_TITLES_EN, WORDS_EN};
use std::sync::OnceLock;

pub static EN_GB: Locale = Locale {
    code: "en_GB",
    name_order: NameOrder::FirstLast,
    style: AddressStyle::Gb,
    first_names: FIRST_NAMES,
    last_names: LAST_NAMES,
    first_names_romanized: None,
    last_names_romanized: None,
    cities: CITIES,
    states: COUNTIES,
    state_abbrs: &[],
    street_names: STREET_NAMES,
    street_suffixes: STREET_SUFFIXES,
    phone_formats: &[
        "+44 20 7### ####", "020 7### ####", "020 8### ####", "07### ######", "+44 7### ######",
        "0161 ^## ####", "0121 ^## ####", "0113 ^## ####", "0131 ^## ####", "0141 ^## ####",
        "029 20## ####", "01%## ^#####",
    ],
    free_email_domains: &[
        "gmail.com", "hotmail.co.uk", "yahoo.co.uk", "outlook.com", "btinternet.com", "sky.com",
        "live.co.uk", "icloud.com", "virginmedia.com", "aol.co.uk",
    ],
    tlds: &[
        "co.uk", "co.uk", "co.uk", "com", "org.uk", "uk", "net", "io",
    ],
    company_formats: &[
        "{L} {S}", "{L} {S}", "{L} & Sons", "{L} and {L} {S}", "{L}-{L}",
    ],
    company_suffixes: &[
        "Ltd", "Ltd", "PLC", "LLP", "Group", "Holdings Ltd", "Partnership",
    ],
    company_words: &[],
    job_titles: JOB_TITLES_EN,
    words: WORDS_EN,
    word_sep: " ",
    sentence_end: ".",
    sentence_sep: " ",
    capitalize: true,
    derived: OnceLock::new(),
};

static FIRST_NAMES: &[&str] = &[
    "Oliver", "George", "Harry", "Jack", "Jacob", "Noah", "Charlie", "Muhammad", "Thomas", "Oscar",
    "William", "James", "Henry", "Leo", "Alfie", "Joshua", "Freddie", "Archie", "Ethan", "Isaac",
    "Alexander", "Joseph", "Edward", "Samuel", "Max", "Daniel", "Arthur", "Lucas", "Mohammed",
    "Logan", "Theo", "Harrison", "Benjamin", "Mason", "Sebastian", "Finley", "Adam", "Dylan",
    "Zachary", "Riley", "Teddy", "Theodore", "David", "Toby", "Jake", "Louie", "Elijah", "Reuben",
    "Arlo", "Hugo", "Luca", "Jaxon", "Matthew", "Harvey", "Reggie", "Michael", "Harley", "Jude",
    "Albert", "Tommy", "Luke", "Stanley", "Jenson", "Frankie", "Gabriel", "Elliot", "Ronnie",
    "Charles", "Louis", "Frederick", "Nathan", "Lewis", "Blake", "Rory", "Ollie", "Ryan", "Tyler",
    "Dexter", "Alex", "Austin", "Kai", "Albie", "Caleb", "Carter", "Bobby", "Ezra", "Ellis", "Leon",
    "Roman", "Ibrahim", "Aaron", "Liam", "Jesse", "Jasper", "Felix", "Jamie", "Callum", "Connor",
    "Kieran", "Rhys", "Owen", "Gareth", "Ian", "Nigel", "Olivia", "Amelia", "Isla", "Ava", "Emily",
    "Isabella", "Mia", "Poppy", "Ella", "Lily", "Evie", "Grace", "Sophia", "Sophie", "Freya",
    "Florence", "Isabelle", "Charlotte", "Daisy", "Phoebe", "Ruby", "Sienna", "Willow", "Matilda",
    "Elsie", "Alice", "Rosie", "Ivy", "Harper", "Evelyn", "Lucy", "Millie", "Esme", "Imogen",
    "Eliza", "Erin", "Maya", "Jessica", "Layla", "Holly", "Emma", "Lola", "Chloe", "Thea",
    "Eleanor", "Megan", "Hannah", "Harriet", "Bethany", "Zara", "Molly", "Abigail", "Amber",
    "Beatrice", "Scarlett", "Georgia", "Katie", "Niamh", "Siobhan", "Fiona", "Gemma", "Kirsty",
    "Rhiannon", "Gwen", "Joanne", "Claire", "Victoria",
];

static LAST_NAMES: &[&str] = &[
    "Smith", "Jones", "Williams", "Taylor", "Brown", "Davies", "Evans", "Wilson", "Thomas",
    "Johnson", "Roberts", "Robinson", "Thompson", "Wright", "Walker", "White", "Edwards", "Hughes",
    "Green", "Hall", "Lewis", "Harris", "Clarke", "Patel", "Jackson", "Wood", "Turner", "Martin",
    "Cooper", "Hill", "Ward", "Morris", "Morgan", "Clark", "Baker", "Harrison", "King", "Allen",
    "Scott", "Mitchell", "Phillips", "Watson", "Young", "James", "Parker", "Bennett", "Price",
    "Davis", "Griffiths", "Cook", "Lee", "Kelly", "Moore", "Carter", "Shaw", "Bell", "Anderson",
    "Lloyd", "Chapman", "Richards", "Bailey", "Ellis", "Owen", "Murphy", "Mason", "Marshall",
    "Simpson", "Hunt", "Collins", "Adams", "Matthews", "Campbell", "Webb", "Rogers", "Stevens",
    "Holmes", "Palmer", "Knight", "Mills", "Barnes", "Russell", "Pearson", "Fox", "Gray", "Dixon",
    "Kaur", "Singh", "Khan", "Ali", "Ahmed", "Murray", "Butler", "Lawrence", "Stewart", "Saunders",
    "Dawson", "Fletcher", "Hamilton", "Gibson", "Spencer", "Ross", "Graham", "Reid", "Kennedy",
    "Cox", "Harvey", "Hussain", "Hayes", "Jenkins", "Pearce", "Payne", "Booth", "Burton", "Dean",
    "Ford", "Lane", "Atkinson", "Andrews", "Barker", "Bradley", "Byrne", "Chambers", "Cole", "Day",
    "Douglas", "Elliott", "Foster", "Gordon", "Grant", "Hart", "Henderson", "Holland", "Howard",
    "Hudson", "Jordan", "Kerr", "Little", "Macdonald", "Miller", "Newman", "Nicholson", "O'Brien",
    "Parsons", "Porter", "Rees", "Reynolds", "Rose", "Sharp", "Sutton", "Walsh", "Watts", "Wells",
    "West", "Wilkinson", "Willis", "Woods", "Wyatt", "Yates", "McLeod", "Fraser", "Thomson",
    "MacKenzie", "Doyle",
];

static CITIES: &[&str] = &[
    "London", "Birmingham", "Manchester", "Leeds", "Liverpool", "Sheffield", "Bristol", "Glasgow",
    "Edinburgh", "Leicester", "Coventry", "Bradford", "Cardiff", "Belfast", "Nottingham",
    "Kingston upon Hull", "Newcastle upon Tyne", "Stoke-on-Trent", "Southampton", "Derby",
    "Portsmouth", "Brighton", "Plymouth", "Northampton", "Reading", "Luton", "Wolverhampton",
    "Bolton", "Aberdeen", "Bournemouth", "Norwich", "Swindon", "Swansea", "Milton Keynes",
    "Southend-on-Sea", "Middlesbrough", "Sunderland", "Peterborough", "Warrington", "Oxford",
    "Cambridge", "York", "Huddersfield", "Slough", "Blackpool", "Ipswich", "Dundee", "Telford",
    "Exeter", "Gloucester", "Chelmsford", "Colchester", "Crawley", "Preston", "Bath", "Canterbury",
    "Chester", "Durham", "Lancaster", "Lincoln", "Salisbury", "Winchester", "Worcester", "Carlisle",
    "Inverness", "Stirling", "Perth", "Newport", "Wrexham", "Bangor", "Londonderry", "Lisburn",
    "Guildford", "Harrogate", "Cheltenham", "Maidstone", "Basingstoke", "Watford", "Woking",
    "St Albans", "Stockport", "Wigan", "Oldham", "Rochdale", "Doncaster", "Rotherham", "Barnsley",
    "Wakefield", "Halifax", "Burnley", "Blackburn", "Hastings", "Eastbourne", "Worthing", "Torquay",
    "Truro", "Hereford", "Shrewsbury",
];

static COUNTIES: &[&str] = &[
    "Greater London", "West Midlands", "Greater Manchester", "West Yorkshire", "Merseyside",
    "South Yorkshire", "Kent", "Essex", "Hampshire", "Lancashire", "Surrey", "Hertfordshire",
    "Norfolk", "Devon", "Cornwall", "Somerset", "Dorset", "Cheshire", "Derbyshire",
    "Nottinghamshire", "Lincolnshire", "Leicestershire", "Staffordshire", "Oxfordshire",
    "Cambridgeshire", "Suffolk", "Wiltshire", "Gloucestershire", "North Yorkshire",
    "Northumberland", "Cumbria", "County Durham", "East Sussex", "West Sussex", "Berkshire",
    "Buckinghamshire", "Bedfordshire", "Worcestershire", "Warwickshire", "Shropshire",
    "Herefordshire", "Tyne and Wear", "City of Edinburgh", "Glasgow City", "Aberdeenshire", "Fife",
    "Highland", "Gwynedd", "Pembrokeshire", "County Antrim", "County Down",
];

static STREET_NAMES: &[&str] = &[
    "High", "Station", "Main", "Park", "Church", "London", "Victoria", "Green", "Manor", "Kings",
    "Queens", "Mill", "School", "Grange", "Windsor", "Albert", "Springfield", "Highfield",
    "Chester", "York", "New", "Alexandra", "North", "South", "West", "East", "Cromwell", "Richmond",
    "Mount Pleasant", "Oxford", "Cambridge", "Beech", "Oak", "Ash", "Elm", "Willow", "Meadow",
    "Orchard", "St John's", "St Mary's", "Brook", "Castle", "Abbey", "Bridge", "Market", "Albion",
    "Clarence", "Cavendish", "Belmont", "Stanley", "Wellington", "Nelson",
];

static STREET_SUFFIXES: &[&str] = &[
    "Road", "Road", "Street", "Street", "Lane", "Avenue", "Close", "Drive", "Gardens", "Way",
    "Crescent", "Grove", "Terrace", "Place", "Hill", "Court", "Mews", "Row", "Walk", "Rise",
];

/// Real UK postcode areas, used by the `postcode` provider.
pub static POSTCODE_AREAS: &[&str] = &[
    "E", "EC", "N", "NW", "SE", "SW", "W", "WC", "B", "M", "L", "LS", "S", "BS", "G", "EH", "CF",
    "BT", "NG", "LE", "CV", "BD", "HU", "NE", "ST", "SO", "DE", "PO", "BN", "PL", "NN", "RG", "LU",
    "WV", "BL", "AB", "BH", "NR", "SN", "SA", "MK", "SS", "TS", "SR", "PE", "WA", "OX", "CB", "YO",
    "HD", "GU", "AL", "CH", "DH", "EX", "GL", "IP", "LN", "TR",
];
