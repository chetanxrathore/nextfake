//! English (United States).

use super::{AddressStyle, Locale, NameOrder, JOB_TITLES_EN, WORDS_EN};
use std::sync::OnceLock;

pub static EN_US: Locale = Locale {
    code: "en_US",
    name_order: NameOrder::FirstLast,
    style: AddressStyle::Us,
    first_names: FIRST_NAMES,
    last_names: LAST_NAMES,
    first_names_romanized: None,
    last_names_romanized: None,
    cities: CITIES,
    states: STATES,
    state_abbrs: STATE_ABBRS,
    street_names: STREET_NAMES,
    street_suffixes: STREET_SUFFIXES,
    phone_formats: &[
        "(^##) ^##-####", "^##-^##-####", "+1-^##-^##-####", "^##.^##.####", "1-^##-^##-####",
        "(^##) ^##-#### x###",
    ],
    free_email_domains: &[
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com",
        "protonmail.com", "msn.com", "live.com", "comcast.net",
    ],
    tlds: &[
        "com", "com", "com", "net", "org", "info", "biz", "io", "co", "us",
    ],
    company_formats: &[
        "{L} {S}", "{L} {S}", "{L}-{L}", "{L}, {L} and {L}", "{L} & {L} {S}",
    ],
    company_suffixes: &[
        "Inc", "LLC", "Group", "Corp", "and Sons", "Holdings", "Partners", "Solutions",
        "Technologies", "Industries", "Enterprises", "Labs",
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
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "David",
    "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah",
    "Christopher", "Karen", "Charles", "Lisa", "Daniel", "Nancy", "Matthew", "Betty", "Anthony",
    "Sandra", "Mark", "Margaret", "Donald", "Ashley", "Steven", "Kimberly", "Andrew", "Emily",
    "Paul", "Donna", "Joshua", "Michelle", "Kenneth", "Carol", "Kevin", "Amanda", "Brian",
    "Melissa", "George", "Deborah", "Timothy", "Stephanie", "Ronald", "Dorothy", "Jason", "Rebecca",
    "Edward", "Sharon", "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Amy", "Gary", "Kathleen",
    "Nicholas", "Angela", "Eric", "Shirley", "Jonathan", "Brenda", "Stephen", "Emma", "Larry",
    "Anna", "Justin", "Pamela", "Scott", "Nicole", "Brandon", "Samantha", "Benjamin", "Katherine",
    "Samuel", "Christine", "Gregory", "Helen", "Alexander", "Debra", "Patrick", "Rachel", "Frank",
    "Carolyn", "Raymond", "Janet", "Jack", "Maria", "Dennis", "Catherine", "Jerry", "Heather",
    "Tyler", "Diane", "Aaron", "Olivia", "Jose", "Julie", "Adam", "Joyce", "Nathan", "Victoria",
    "Henry", "Ruth", "Zachary", "Virginia", "Douglas", "Lauren", "Peter", "Kelly", "Kyle",
    "Christina", "Noah", "Joan", "Ethan", "Evelyn", "Jeremy", "Judith", "Christian", "Andrea",
    "Walter", "Hannah", "Keith", "Megan", "Austin", "Cheryl", "Roger", "Jacqueline", "Terry",
    "Martha", "Sean", "Madison", "Gerald", "Teresa", "Carl", "Gloria", "Dylan", "Sara", "Harold",
    "Janice", "Jordan", "Ann", "Jesse", "Kathryn", "Bryan", "Abigail", "Lawrence", "Sophia",
    "Arthur", "Frances", "Gabriel", "Jean", "Bruce", "Alice", "Logan", "Judy", "Billy", "Isabella",
    "Joe", "Julia", "Alan", "Grace", "Juan", "Amber", "Elijah", "Denise", "Willie", "Danielle",
    "Albert", "Marilyn", "Wayne", "Beverly", "Randy", "Charlotte", "Mason", "Natalie", "Vincent",
    "Theresa", "Liam", "Diana", "Roy", "Brittany", "Bobby", "Doris", "Caleb", "Kayla", "Bradley",
    "Alexis", "Russell", "Lori", "Lucas", "Marie", "Carlos", "Ava", "Luis", "Mia", "Miguel",
    "Harper", "Aiden", "Chloe", "Jayden", "Zoe",
];

static LAST_NAMES: &[&str] = &[
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez",
    "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore",
    "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres",
    "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell",
    "Mitchell", "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker",
    "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy", "Cook",
    "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson", "Bailey", "Reed", "Kelly",
    "Howard", "Ramos", "Kim", "Cox", "Ward", "Richardson", "Watson", "Brooks", "Chavez", "Wood",
    "James", "Bennett", "Gray", "Mendoza", "Ruiz", "Hughes", "Price", "Alvarez", "Castillo",
    "Sanders", "Patel", "Myers", "Long", "Ross", "Foster", "Jimenez", "Powell", "Jenkins", "Perry",
    "Russell", "Sullivan", "Bell", "Coleman", "Butler", "Henderson", "Barnes", "Gonzales", "Fisher",
    "Vasquez", "Simmons", "Romero", "Jordan", "Patterson", "Alexander", "Hamilton", "Graham",
    "Reynolds", "Griffin", "Wallace", "Moreno", "West", "Cole", "Hayes", "Bryant", "Herrera",
    "Gibson", "Ellis", "Tran", "Medina", "Aguilar", "Stevens", "Murray", "Ford", "Castro",
    "Marshall", "Owens", "Harrison", "Fernandez", "McDonald", "Woods", "Washington", "Kennedy",
    "Wells", "Vargas", "Henry", "Chen", "Freeman", "Webb", "Tucker", "Guzman", "Burns", "Crawford",
    "Olson", "Simpson", "Porter", "Hunter", "Gordon", "Mendez", "Silva", "Shaw", "Snyder", "Mason",
    "Dixon", "Munoz", "Hunt", "Hicks", "Holmes", "Palmer", "Wagner", "Black", "Robertson", "Boyd",
    "Rose", "Stone", "Salazar", "Fox", "Warren", "Mills", "Meyer", "Rice", "Schmidt", "Garza",
    "Daniels", "Ferguson", "Nichols", "Stephens", "Soto", "Weaver", "Ryan", "Gardner", "Payne",
    "Grant", "Dunn", "Kelley", "Spencer", "Hawkins", "Arnold", "Pierce", "Vazquez", "Hansen",
    "Peters", "Santos", "Hart", "Bradley", "Knight", "Elliott", "Cunningham", "Duncan", "Armstrong",
    "Hudson", "Carroll", "Lane", "Riley", "Andrews", "Alvarado", "Ray", "Delgado", "Berry",
    "Perkins", "Hoffman", "Johnston", "Matthews", "Pena", "Richards", "Contreras", "Willis",
    "Carpenter", "Lawrence", "Sandoval", "O'Connor", "Wong", "Singh", "Yang", "Huang", "Le", "Park",
    "Shah", "Khan", "Ali",
];

static CITIES: &[&str] = &[
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio",
    "San Diego", "Dallas", "Jacksonville", "Austin", "Fort Worth", "San Jose", "Columbus",
    "Charlotte", "Indianapolis", "San Francisco", "Seattle", "Denver", "Oklahoma City", "Nashville",
    "Washington", "El Paso", "Las Vegas", "Boston", "Detroit", "Portland", "Louisville", "Memphis",
    "Baltimore", "Milwaukee", "Albuquerque", "Tucson", "Fresno", "Sacramento", "Mesa", "Atlanta",
    "Kansas City", "Colorado Springs", "Omaha", "Raleigh", "Miami", "Virginia Beach", "Long Beach",
    "Oakland", "Minneapolis", "Bakersfield", "Tulsa", "Tampa", "Arlington", "Wichita", "Aurora",
    "New Orleans", "Cleveland", "Honolulu", "Anaheim", "Henderson", "Orlando", "Lexington",
    "Stockton", "Riverside", "Corpus Christi", "Irvine", "Cincinnati", "Santa Ana", "Newark",
    "Saint Paul", "Pittsburgh", "Greensboro", "Durham", "Lincoln", "Jersey City", "Plano",
    "Anchorage", "North Las Vegas", "St. Louis", "Madison", "Chandler", "Gilbert", "Reno",
    "Buffalo", "Chula Vista", "Fort Wayne", "Lubbock", "Toledo", "St. Petersburg", "Laredo",
    "Irving", "Chesapeake", "Glendale", "Winston-Salem", "Scottsdale", "Garland", "Boise",
    "Norfolk", "Spokane", "Richmond", "Fremont", "Huntsville", "Frisco", "Cape Coral",
    "Santa Clarita", "San Bernardino", "Tacoma", "Hialeah", "Baton Rouge", "Modesto", "Fontana",
    "McKinney", "Moreno Valley", "Des Moines", "Fayetteville", "Salt Lake City", "Yonkers",
    "Worcester", "Rochester", "Sioux Falls", "Little Rock", "Amarillo", "Tallahassee",
    "Grand Rapids", "Huntington Beach", "Augusta", "Overland Park", "Knoxville", "Providence",
    "Springfield", "Savannah", "Burlington", "Ann Arbor", "Boulder", "Eugene", "Naperville",
    "Pasadena", "Palo Alto", "Berkeley", "Santa Fe", "Charleston", "Asheville", "Bozeman",
    "Missoula", "Duluth", "Syracuse", "Albany", "Hartford",
];

static STATES: &[&str] = &[
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
    "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
    "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi",
    "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico",
    "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania",
    "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
];

static STATE_ABBRS: &[&str] = &[
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS",
    "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY",
    "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY",
];

static STREET_NAMES: &[&str] = &[
    "Main", "Oak", "Pine", "Maple", "Cedar", "Elm", "Washington", "Lake", "Hill", "Park", "Walnut",
    "Sunset", "Lincoln", "Jackson", "Church", "River", "Willow", "Highland", "Forest", "Jefferson",
    "Madison", "Spring", "Franklin", "Adams", "Meadow", "Ridge", "Chestnut", "Birch", "Dogwood",
    "Lakeview", "Center", "Mill", "Valley", "Railroad", "Broad", "Union", "Market", "Water",
    "Prospect", "Locust", "Hickory", "Magnolia", "Cherry", "Spruce", "Laurel", "Sycamore", "Poplar",
    "Grove", "Fairview", "Woodland", "Liberty", "Heritage", "Colonial", "Riverside", "Front",
    "Bridge", "Harbor", "Mountain View", "Pleasant", "Green", "1st", "2nd", "3rd", "4th", "5th",
    "6th", "7th", "8th", "9th", "10th", "11th", "12th",
];

static STREET_SUFFIXES: &[&str] = &[
    "Street", "Street", "Avenue", "Avenue", "Road", "Boulevard", "Lane", "Drive", "Court", "Place",
    "Way", "Circle", "Terrace", "Trail", "Parkway",
];
