//! French (France).

use super::{AddressStyle, Locale, NameOrder};
use std::sync::OnceLock;

pub static FR_FR: Locale = Locale {
    code: "fr_FR",
    name_order: NameOrder::FirstLast,
    style: AddressStyle::Fr,
    first_names: FIRST_NAMES,
    last_names: LAST_NAMES,
    first_names_romanized: None,
    last_names_romanized: None,
    cities: CITIES,
    states: REGIONS,
    state_abbrs: &[],
    street_names: STREET_NAMES,
    street_suffixes: STREET_TYPES,
    phone_formats: &[
        "+33 1 ## ## ## ##", "+33 6 ## ## ## ##", "+33 7 ## ## ## ##", "01 ## ## ## ##",
        "02 ## ## ## ##", "03 ## ## ## ##", "04 ## ## ## ##", "05 ## ## ## ##", "06 ## ## ## ##",
        "07 ## ## ## ##", "09 ## ## ## ##",
    ],
    free_email_domains: &[
        "gmail.com", "orange.fr", "free.fr", "sfr.fr", "laposte.net", "wanadoo.fr", "hotmail.fr",
        "yahoo.fr", "outlook.fr", "bbox.fr",
    ],
    tlds: &["fr", "fr", "fr", "com", "net", "org", "eu"],
    company_formats: &[
        "{L} {S}", "{L} {S}", "{L} et Fils", "{L} & {L}", "Groupe {L}", "{L} {W} {S}",
    ],
    company_suffixes: &["SA", "SARL", "SAS", "SNC", "EURL", "SASU"],
    company_words: &[
        "Bâtiment", "Transports", "Immobilier", "Conseil", "Informatique", "Distribution",
        "Industries", "Services", "Énergie", "Assurances", "Communication",
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
    "Gabriel", "Léo", "Raphaël", "Louis", "Arthur", "Jules", "Adam", "Maël", "Lucas", "Hugo",
    "Noah", "Liam", "Gabin", "Sacha", "Paul", "Nathan", "Aaron", "Mohamed", "Ethan", "Tom", "Théo",
    "Noé", "Victor", "Martin", "Mathis", "Timéo", "Nolan", "Enzo", "Axel", "Antoine", "Baptiste",
    "Thomas", "Nicolas", "Julien", "Alexandre", "Maxime", "Pierre", "Jean", "Philippe", "Michel",
    "Alain", "Patrick", "François", "Christophe", "Laurent", "Olivier", "Sébastien", "Frédéric",
    "Éric", "Stéphane", "David", "Guillaume", "Romain", "Mathieu", "Vincent", "Benoît", "Yves",
    "Jacques", "Bernard", "Claude", "Daniel", "Didier", "Thierry", "Jérôme", "Cédric", "Damien",
    "Florian", "Kévin", "Quentin", "Clément", "Jade", "Louise", "Emma", "Ambre", "Alice", "Rose",
    "Anna", "Alba", "Romy", "Mia", "Lina", "Léa", "Chloé", "Inès", "Manon", "Camille", "Juliette",
    "Zoé", "Lucie", "Sarah", "Agathe", "Margaux", "Clara", "Lola", "Éva", "Marie", "Nathalie",
    "Isabelle", "Sylvie", "Catherine", "Françoise", "Valérie", "Sandrine", "Christine", "Véronique",
    "Sophie", "Céline", "Stéphanie", "Aurélie", "Émilie", "Julie", "Élodie", "Caroline", "Hélène",
    "Anne", "Monique", "Brigitte", "Martine", "Nicole", "Chantal", "Dominique", "Pauline",
    "Mathilde", "Charlotte", "Élise", "Océane", "Marine", "Laure", "Audrey", "Gaëlle", "Noémie",
    "Jean-Pierre", "Marie-Claire",
];

static LAST_NAMES: &[&str] = &[
    "Martin", "Bernard", "Thomas", "Petit", "Robert", "Richard", "Durand", "Dubois", "Moreau",
    "Laurent", "Simon", "Michel", "Lefebvre", "Leroy", "Roux", "David", "Bertrand", "Morel",
    "Fournier", "Girard", "Bonnet", "Dupont", "Lambert", "Fontaine", "Rousseau", "Vincent",
    "Muller", "Lefèvre", "Faure", "André", "Mercier", "Blanc", "Guérin", "Boyer", "Garnier",
    "Chevalier", "François", "Legrand", "Gauthier", "Garcia", "Perrin", "Robin", "Clément", "Morin",
    "Nicolas", "Henry", "Roussel", "Mathieu", "Gautier", "Masson", "Marchand", "Duval", "Denis",
    "Dumont", "Marie", "Lemaire", "Noël", "Meyer", "Dufour", "Meunier", "Brun", "Blanchard",
    "Giraud", "Joly", "Rivière", "Lucas", "Brunet", "Gaillard", "Barbier", "Arnaud", "Martinez",
    "Gérard", "Roche", "Renard", "Schmitt", "Roy", "Leroux", "Colin", "Vidal", "Caron", "Picard",
    "Roger", "Fabre", "Aubert", "Lemoine", "Renaud", "Dumas", "Lacroix", "Olivier", "Philippe",
    "Bourgeois", "Pierre", "Benoît", "Rey", "Leclerc", "Payet", "Rolland", "Leclercq", "Guillaume",
    "Lecomte", "Lopez", "Jean", "Dupuy", "Guillot", "Hubert", "Berger", "Carpentier", "Sanchez",
    "Dupuis", "Moulin", "Louis", "Deschamps", "Huet", "Vasseur", "Perez", "Boucher", "Fleury",
    "Royer", "Klein", "Jacquet", "Adam", "Paris", "Poirier", "Marty", "Aubry", "Guyot", "Carré",
    "Charles", "Renault", "Charpentier", "Ménard", "Maillard", "Baron", "Bertin", "Bailly", "Hervé",
    "Schneider", "Fernandez", "Le Gall", "Collet", "Léger", "Bouvier", "Julien", "Prévost",
    "Millet", "Perrot", "Daniel", "Le Roux", "Cousin", "Germain", "Breton", "Besson", "Langlois",
    "Rémy", "Le Goff", "Pelletier", "Lévêque", "Perrier", "Leblanc", "Barré", "Lebrun", "Marchal",
    "Weber", "Mallet", "Hamon", "Boulanger", "Jacob", "Monnier", "Michaud", "Rodriguez", "Guichard",
    "Gillet", "Étienne", "Grondin", "Poulain", "Tessier", "Chevallier", "Collin", "Chauvin",
    "Da Silva", "Bouchet", "Gay", "Lemaître", "Bénard", "Gosselin", "Lefort", "N'Diaye",
];

static CITIES: &[&str] = &[
    "Paris", "Marseille", "Lyon", "Toulouse", "Nice", "Nantes", "Montpellier", "Strasbourg",
    "Bordeaux", "Lille", "Rennes", "Toulon", "Reims", "Saint-Étienne", "Le Havre", "Villeurbanne",
    "Dijon", "Grenoble", "Angers", "Saint-Denis", "Nîmes", "Clermont-Ferrand", "Aix-en-Provence",
    "Le Mans", "Brest", "Tours", "Amiens", "Limoges", "Annecy", "Boulogne-Billancourt", "Perpignan",
    "Metz", "Besançon", "Orléans", "Rouen", "Mulhouse", "Caen", "Nancy", "Argenteuil", "Montreuil",
    "Roubaix", "Tourcoing", "Avignon", "Nanterre", "Vitry-sur-Seine", "Créteil", "Poitiers",
    "Versailles", "Courbevoie", "Pau", "Colombes", "Aulnay-sous-Bois", "Asnières-sur-Seine",
    "Rueil-Malmaison", "La Rochelle", "Antibes", "Saint-Maur-des-Fossés", "Calais", "Cannes",
    "Béziers", "Champigny-sur-Marne", "Colmar", "Bourges", "Mérignac", "Ajaccio", "Saint-Nazaire",
    "Issy-les-Moulineaux", "Noisy-le-Grand", "Quimper", "Valence", "Vénissieux", "Cergy",
    "Levallois-Perret", "Pessac", "Troyes", "Antony", "Ivry-sur-Seine", "Clichy", "Chambéry",
    "Lorient", "Niort", "Sarcelles", "Villejuif", "Saint-Quentin", "Hyères", "Épinay-sur-Seine",
    "Beauvais", "Cholet", "Vannes", "Chartres", "Arles", "Bayonne", "Biarritz", "Saint-Malo",
    "Carcassonne", "Albi", "Lourdes", "Chamonix-Mont-Blanc", "Montauban", "Évry-Courcouronnes",
];

static REGIONS: &[&str] = &[
    "Auvergne-Rhône-Alpes", "Bourgogne-Franche-Comté", "Bretagne", "Centre-Val de Loire", "Corse",
    "Grand Est", "Hauts-de-France", "Île-de-France", "Normandie", "Nouvelle-Aquitaine", "Occitanie",
    "Pays de la Loire", "Provence-Alpes-Côte d'Azur", "Guadeloupe", "Martinique", "Guyane",
    "La Réunion", "Mayotte",
];

static STREET_TYPES: &[&str] = &[
    "rue", "rue", "rue", "avenue", "avenue", "boulevard", "place", "impasse", "allée", "chemin",
    "quai", "route", "cours", "passage", "square",
];

static STREET_NAMES: &[&str] = &[
    "de la Paix", "Victor Hugo", "de la République", "Jean Jaurès", "du Général de Gaulle",
    "Pasteur", "de la Gare", "des Écoles", "du Moulin", "de l'Église", "Gambetta", "Voltaire",
    "Jules Ferry", "de la Liberté", "des Lilas", "du Château", "Nationale", "de Paris",
    "Émile Zola", "Carnot", "Louis Pasteur", "Charles de Gaulle", "du Stade", "des Roses",
    "de Verdun", "Saint-Michel", "Saint-Martin", "de la Fontaine", "des Tilleuls", "du Commerce",
    "Foch", "Clemenceau", "Henri IV", "Molière", "Lamartine", "Jean Moulin", "de la Mairie",
    "des Acacias", "du Port", "de Bretagne", "Marcel Pagnol", "Anatole France", "Mozart",
    "des Peupliers", "du Maréchal Leclerc", "de la Croix-Rousse", "de Rivoli", "Haussmann",
    "Saint-Honoré", "des Vignes", "du Lac", "de la Forêt",
];

static JOB_TITLES: &[&str] = &[
    "Ingénieur logiciel", "Chef de projet", "Développeuse web", "Comptable", "Infirmière",
    "Médecin généraliste", "Avocat", "Architecte", "Professeur des écoles", "Commercial",
    "Responsable marketing", "Directeur financier", "Pharmacienne", "Boulanger", "Cuisinier",
    "Chargée de communication", "Analyste de données", "Technicien de maintenance", "Électricien",
    "Plombier", "Journaliste", "Graphiste", "Consultant", "Assistante de direction",
    "Responsable des ressources humaines", "Agent immobilier", "Kinésithérapeute", "Vétérinaire",
    "Pilote de ligne", "Chauffeur", "Serveur", "Libraire", "Traductrice", "Ingénieure civile",
    "Administrateur système", "Juriste", "Notaire", "Designer UX", "Data scientist",
    "Product manager",
];

static WORDS: &[&str] = &[
    "le", "la", "les", "un", "une", "des", "et", "est", "dans", "pour", "avec", "sur", "pas",
    "plus", "très", "temps", "jour", "année", "maison", "monde", "vie", "ville", "travail", "homme",
    "femme", "enfant", "question", "exemple", "bon", "nouveau", "grand", "petit", "vieux", "rapide",
    "beau", "long", "important", "possible", "toujours", "aujourd'hui", "encore", "déjà",
    "seulement", "ici", "faire", "dire", "aller", "venir", "voir", "trouver", "rester", "donner",
    "prendre", "penser", "travailler", "apprendre", "jouer", "eau", "soleil", "jardin", "rue",
    "voiture", "livre", "école", "ami", "famille", "matin", "soir", "nuit", "avenir", "idée",
    "projet", "savoir", "nature", "musique", "voyage", "repas", "café", "pain", "forêt", "montagne",
    "rivière", "ciel", "lumière", "couleur", "histoire", "langue", "image", "espace", "chemin",
    "fin", "début", "fenêtre", "porte", "mer", "été", "hiver",
];
