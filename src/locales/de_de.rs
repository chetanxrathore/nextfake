//! German (Germany).

use super::{AddressStyle, Locale, NameOrder};
use std::sync::OnceLock;

pub static DE_DE: Locale = Locale {
    code: "de_DE",
    name_order: NameOrder::FirstLast,
    style: AddressStyle::De,
    first_names: FIRST_NAMES,
    last_names: LAST_NAMES,
    first_names_romanized: None,
    last_names_romanized: None,
    cities: CITIES,
    states: STATES,
    state_abbrs: STATE_ABBRS,
    street_names: STREET_NAMES,
    street_suffixes: &[],
    phone_formats: &[
        "+49 30 ########", "030 ########", "089 ########", "040 ########", "0221 #######",
        "069 ########", "0711 #######", "0151 ########", "0160 ########", "0170 ########",
        "0171 ########", "0176 ########", "+49 151 ########", "+49 (0)%### ######",
    ],
    free_email_domains: &[
        "gmail.com", "web.de", "gmx.de", "gmx.net", "t-online.de", "yahoo.de", "outlook.de",
        "hotmail.de", "freenet.de", "posteo.de",
    ],
    tlds: &["de", "de", "de", "com", "net", "org", "eu", "info"],
    company_formats: &[
        "{L} {S}", "{L} {S}", "{L} & {L} {S}", "{L} GmbH & Co. KG", "{L} {W} GmbH", "{L}-{L} {S}",
    ],
    company_suffixes: &[
        "GmbH", "GmbH", "AG", "KG", "OHG", "e.K.", "SE", "UG (haftungsbeschränkt)",
    ],
    company_words: &[
        "Bau", "Logistik", "Elektro", "Immobilien", "Maschinenbau", "Software", "Consulting",
        "Medien", "Handel", "Technik", "Versicherung", "Automobil", "Holzbau", "Energie",
    ],
    job_titles: JOB_TITLES,
    words: WORDS,
    word_sep: " ",
    sentence_end: ".",
    sentence_sep: " ",
    capitalize: true,
    derived: OnceLock::new(),
};

static FIRST_NAMES: &[&str] = &[
    "Lukas", "Leon", "Finn", "Jonas", "Paul", "Elias", "Noah", "Ben", "Felix", "Luis", "Maximilian",
    "Henry", "Emil", "Theo", "Anton", "Jakob", "Oskar", "Matteo", "Moritz", "Julian", "Niklas",
    "Tim", "Jan", "David", "Alexander", "Fabian", "Florian", "Sebastian", "Tobias", "Daniel",
    "Michael", "Thomas", "Andreas", "Stefan", "Markus", "Christian", "Martin", "Frank", "Jürgen",
    "Klaus", "Wolfgang", "Dieter", "Uwe", "Peter", "Günter", "Hans", "Karl", "Heinz", "Werner",
    "Manfred", "Horst", "Helmut", "Rainer", "Bernd", "Ralf", "Holger", "Jens", "Sven", "Torsten",
    "Dirk", "Kai", "Lars", "Matthias", "Johannes", "Philipp", "Simon", "Patrick", "Dominik",
    "Marcel", "Kevin", "Björn", "Jörg", "Mehmet", "Can", "Mia", "Emma", "Hannah", "Sofia", "Emilia",
    "Lina", "Mila", "Ella", "Clara", "Lea", "Marie", "Leni", "Anna", "Lena", "Laura", "Lara",
    "Johanna", "Charlotte", "Luisa", "Amelie", "Maja", "Sophie", "Ida", "Frieda", "Greta", "Paula",
    "Mathilda", "Katharina", "Julia", "Sarah", "Lisa", "Jana", "Nina", "Sandra", "Sabine",
    "Susanne", "Petra", "Claudia", "Andrea", "Stefanie", "Nicole", "Kerstin", "Birgit", "Monika",
    "Ursula", "Renate", "Brigitte", "Ingrid", "Gisela", "Helga", "Karin", "Heike", "Anja", "Katrin",
    "Silke", "Melanie", "Christina", "Franziska", "Jessica", "Vanessa", "Annika", "Jasmin",
    "Carolin", "Theresa", "Miriam", "Elisabeth", "Ute", "Gabriele", "Barbara", "Lotte", "Ayşe",
    "Zoë",
];

static LAST_NAMES: &[&str] = &[
    "Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker", "Schulz",
    "Hoffmann", "Schäfer", "Koch", "Bauer", "Richter", "Klein", "Wolf", "Schröder", "Neumann",
    "Schwarz", "Zimmermann", "Braun", "Krüger", "Hofmann", "Hartmann", "Lange", "Schmitt", "Werner",
    "Schmitz", "Krause", "Meier", "Lehmann", "Schmid", "Schulze", "Maier", "Köhler", "Herrmann",
    "König", "Walter", "Mayer", "Huber", "Kaiser", "Fuchs", "Peters", "Lang", "Scholz", "Möller",
    "Weiß", "Jung", "Hahn", "Schubert", "Vogel", "Friedrich", "Keller", "Günther", "Frank",
    "Berger", "Winkler", "Roth", "Beck", "Lorenz", "Baumann", "Franke", "Albrecht", "Schuster",
    "Simon", "Ludwig", "Böhm", "Winter", "Kraus", "Martin", "Schumacher", "Krämer", "Vogt", "Stein",
    "Jäger", "Otto", "Sommer", "Groß", "Seidel", "Heinrich", "Brandt", "Haas", "Schreiber", "Graf",
    "Schulte", "Dietrich", "Ziegler", "Kuhn", "Kühn", "Pohl", "Engel", "Horn", "Busch", "Bergmann",
    "Thomas", "Voigt", "Sauer", "Arnold", "Wolff", "Pfeiffer", "Ernst", "Kaya", "Yılmaz", "Öztürk",
    "Demir", "Nowak", "Kowalski", "Popescu", "Lindner", "Brinkmann", "Hesse", "Kretschmer", "Bach",
    "Kolb", "Marx", "Langer", "Böttcher",
];

static CITIES: &[&str] = &[
    "Berlin", "Hamburg", "München", "Köln", "Frankfurt am Main", "Stuttgart", "Düsseldorf",
    "Leipzig", "Dortmund", "Essen", "Bremen", "Dresden", "Hannover", "Nürnberg", "Duisburg",
    "Bochum", "Wuppertal", "Bielefeld", "Bonn", "Münster", "Mannheim", "Karlsruhe", "Augsburg",
    "Wiesbaden", "Mönchengladbach", "Gelsenkirchen", "Aachen", "Braunschweig", "Kiel", "Chemnitz",
    "Halle (Saale)", "Magdeburg", "Freiburg im Breisgau", "Krefeld", "Mainz", "Lübeck", "Erfurt",
    "Oberhausen", "Rostock", "Kassel", "Hagen", "Potsdam", "Saarbrücken", "Hamm",
    "Ludwigshafen am Rhein", "Oldenburg", "Mülheim an der Ruhr", "Osnabrück", "Leverkusen",
    "Darmstadt", "Heidelberg", "Solingen", "Herne", "Regensburg", "Neuss", "Paderborn",
    "Ingolstadt", "Offenbach am Main", "Fürth", "Würzburg", "Ulm", "Heilbronn", "Pforzheim",
    "Wolfsburg", "Göttingen", "Bottrop", "Reutlingen", "Koblenz", "Bremerhaven", "Erlangen",
    "Bergisch Gladbach", "Trier", "Recklinghausen", "Jena", "Remscheid", "Salzgitter", "Moers",
    "Siegen", "Hildesheim", "Gütersloh", "Kaiserslautern", "Cottbus", "Witten", "Schwerin",
    "Zwickau", "Gera", "Flensburg", "Konstanz", "Passau", "Bamberg", "Bayreuth", "Lüneburg",
    "Weimar", "Marburg", "Gießen", "Tübingen", "Celle", "Wismar", "Stralsund",
];

static STATES: &[&str] = &[
    "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen", "Hamburg", "Hessen",
    "Mecklenburg-Vorpommern", "Niedersachsen", "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland",
    "Sachsen", "Sachsen-Anhalt", "Schleswig-Holstein", "Thüringen",
];

static STATE_ABBRS: &[&str] = &[
    "BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV", "NI", "NW", "RP", "SL", "SN", "ST", "SH", "TH",
];

static STREET_NAMES: &[&str] = &[
    "Hauptstraße", "Schulstraße", "Gartenstraße", "Bahnhofstraße", "Dorfstraße", "Bergstraße",
    "Birkenweg", "Lindenstraße", "Kirchstraße", "Waldstraße", "Ringstraße", "Schillerstraße",
    "Goethestraße", "Am Markt", "Jahnstraße", "Wiesenweg", "Feldstraße", "Mühlenweg", "Rosenstraße",
    "Blumenstraße", "Lessingstraße", "Mozartstraße", "Beethovenstraße", "Friedhofstraße",
    "Industriestraße", "Poststraße", "Kastanienallee", "Ahornweg", "Eichenweg", "Tannenweg",
    "Buchenweg", "Amselweg", "Finkenweg", "Mittelweg", "Sonnenstraße", "Uhlandstraße", "Talstraße",
    "Brunnenstraße", "Marktplatz", "Lindenallee", "Parkstraße", "Kantstraße", "Friedrichstraße",
    "Wilhelmstraße", "Karlstraße", "Ludwigstraße", "Bismarckstraße", "Rathausstraße", "Burgstraße",
    "Schloßstraße", "Breite Straße", "Lange Straße", "Neue Straße", "Alte Landstraße",
    "Kurze Straße", "Am Bahnhof", "Im Winkel", "Hafenstraße", "Heinestraße",
];

static JOB_TITLES: &[&str] = &[
    "Softwareentwickler", "Projektmanagerin", "Bankkaufmann", "Industriemechaniker", "Elektriker",
    "Krankenpfleger", "Lehrerin", "Steuerberater", "Rechtsanwältin", "Ärztin", "Architekt",
    "Ingenieur", "Vertriebsleiter", "Buchhalterin", "Marketingmanager", "Personalreferentin",
    "Kfz-Mechatroniker", "Bäcker", "Koch", "Fachkraft für Lagerlogistik", "Datenanalyst",
    "Systemadministrator", "Grafikdesignerin", "Erzieherin", "Physiotherapeut", "Apothekerin",
    "Journalist", "Polizeibeamter", "Tischler", "Verkäuferin", "Einkaufsleiter", "Geschäftsführer",
    "Produktmanager", "Unternehmensberater", "Controller", "Bauingenieurin", "Mediengestalter",
    "Zahnarzt", "Hotelfachfrau", "Fachinformatiker",
];

static WORDS: &[&str] = &[
    "und", "der", "die", "das", "ist", "nicht", "ein", "eine", "mit", "auf", "für", "von", "zu",
    "im", "den", "sich", "auch", "es", "wir", "sie", "Zeit", "Jahr", "Tag", "Haus", "Welt", "Leben",
    "Stadt", "Arbeit", "Menschen", "Frage", "Beispiel", "gut", "neu", "groß", "klein", "alt",
    "schnell", "schön", "lang", "wichtig", "möglich", "immer", "heute", "wieder", "schon", "noch",
    "nur", "sehr", "hier", "dort", "machen", "sagen", "gehen", "kommen", "sehen", "finden",
    "bleiben", "geben", "nehmen", "denken", "arbeiten", "lernen", "spielen", "Wasser", "Sonne",
    "Garten", "Straße", "Auto", "Buch", "Schule", "Freund", "Familie", "Kinder", "Wochenende",
    "Morgen", "Abend", "Nacht", "Zukunft", "Idee", "Projekt", "Wissen", "Natur", "Musik", "Reise",
    "Essen", "Kaffee", "Brot", "Wald", "Berg", "Fluss", "Himmel", "Licht", "Farbe", "Geschichte",
    "Sprache", "Bild", "Raum", "Weg", "Ende", "Anfang", "Fenster", "Tür",
];
