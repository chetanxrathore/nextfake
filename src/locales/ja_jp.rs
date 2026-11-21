//! Japanese (Japan).

use super::{AddressStyle, Locale, NameOrder};
use std::sync::OnceLock;

pub static JA_JP: Locale = Locale {
    code: "ja_JP",
    name_order: NameOrder::LastFirst,
    style: AddressStyle::Jp,
    first_names: FIRST_NAMES,
    last_names: LAST_NAMES,
    first_names_romanized: Some(FIRST_NAMES_ROMAJI),
    last_names_romanized: Some(LAST_NAMES_ROMAJI),
    cities: CITIES,
    states: PREFECTURES,
    state_abbrs: &[],
    street_names: TOWNS,
    street_suffixes: &[],
    phone_formats: &[
        "090-####-####", "080-####-####", "070-####-####", "03-####-####", "06-####-####",
        "052-###-####", "011-###-####", "092-###-####", "0%#-###-####", "0%##-##-####",
        "+81-90-####-####",
    ],
    free_email_domains: &[
        "gmail.com", "yahoo.co.jp", "docomo.ne.jp", "ezweb.ne.jp", "softbank.ne.jp", "icloud.com",
        "outlook.jp", "hotmail.co.jp", "i.softbank.jp", "au.com",
    ],
    tlds: &["jp", "co.jp", "co.jp", "com", "ne.jp", "or.jp", "net"],
    company_formats: &[
        "株式会社{L}{W}", "{L}{W}株式会社", "有限会社{L}{W}", "合同会社{L}{W}",
    ],
    company_suffixes: &[],
    company_words: &[
        "商事", "工業", "建設", "電機", "製作所", "産業", "物産", "運輸", "不動産", "食品", "製薬", "化学", "技研", "システム",
        "ホールディングス", "電子", "印刷", "興業", "通信",
    ],
    job_titles: JOB_TITLES,
    words: WORDS,
    word_sep: "",
    sentence_end: "。",
    sentence_sep: "",
    capitalize: false,
    derived: OnceLock::new(),
};

static LAST_NAMES: &[&str] = &[
    "佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤", "吉田", "山田", "佐々木", "山口", "松本", "井上",
    "木村", "林", "斎藤", "清水", "山崎", "森", "池田", "橋本", "阿部", "石川", "山下", "中島", "石井", "小川", "前田", "岡田",
    "長谷川", "藤田", "後藤", "近藤", "村上", "遠藤", "青木", "坂本", "福田", "太田", "西村", "藤井", "金子", "岡本", "藤原", "中野",
    "三浦", "原田", "中川", "松田", "竹内", "小野", "田村", "中山", "和田", "石田", "森田", "上田", "原", "内田", "柴田", "酒井",
    "宮崎", "横山", "高木", "安藤", "宮本", "大野", "小島", "谷口", "今井", "工藤", "高田", "増田", "丸山", "杉山", "村田", "大塚",
    "新井", "小山", "平野", "藤本", "河野", "上野", "野口", "武田", "松井", "千葉", "岩崎", "菅原", "木下", "久保", "佐野", "野村",
    "松尾", "市川", "菊地",
];

static LAST_NAMES_ROMAJI: &[&str] = &[
    "sato", "suzuki", "takahashi", "tanaka", "ito", "watanabe", "yamamoto", "nakamura", "kobayashi",
    "kato", "yoshida", "yamada", "sasaki", "yamaguchi", "matsumoto", "inoue", "kimura", "hayashi",
    "saito", "shimizu", "yamazaki", "mori", "ikeda", "hashimoto", "abe", "ishikawa", "yamashita",
    "nakajima", "ishii", "ogawa", "maeda", "okada", "hasegawa", "fujita", "goto", "kondo",
    "murakami", "endo", "aoki", "sakamoto", "fukuda", "ota", "nishimura", "fujii", "kaneko",
    "okamoto", "fujiwara", "nakano", "miura", "harada", "nakagawa", "matsuda", "takeuchi", "ono",
    "tamura", "nakayama", "wada", "ishida", "morita", "ueda", "hara", "uchida", "shibata", "sakai",
    "miyazaki", "yokoyama", "takagi", "ando", "miyamoto", "ohno", "kojima", "taniguchi", "imai",
    "kudo", "takada", "masuda", "maruyama", "sugiyama", "murata", "otsuka", "arai", "koyama",
    "hirano", "fujimoto", "kono", "ueno", "noguchi", "takeda", "matsui", "chiba", "iwasaki",
    "sugawara", "kinoshita", "kubo", "sano", "nomura", "matsuo", "ichikawa", "kikuchi",
];

static FIRST_NAMES: &[&str] = &[
    "翔太", "大翔", "蓮", "陽翔", "湊", "樹", "悠真", "陽太", "颯太", "結翔", "大和", "健太", "拓海", "直樹", "大輔", "翼", "誠",
    "和也", "達也", "浩", "健一", "隆", "学", "修", "稔", "剛", "一郎", "太郎", "次郎", "健二", "雄一", "亮", "涼介", "康介",
    "裕太", "翔", "海斗", "優斗", "悠斗", "晴", "陽菜", "結衣", "葵", "凛", "結菜", "芽依", "莉子", "美咲", "さくら", "愛",
    "花子", "優子", "恵", "陽子", "直美", "久美子", "由美", "真由美", "明美", "智子", "京子", "洋子", "幸子", "裕子", "美穂", "彩",
    "舞", "麻衣", "香織", "沙織", "奈々", "千尋", "愛子", "美月", "七海", "遥", "楓", "杏", "紬", "澪", "心春", "美優", "彩花",
    "菜々子", "真央", "千夏", "未来", "桜子", "琴音", "栞",
];

static FIRST_NAMES_ROMAJI: &[&str] = &[
    "shota", "hiroto", "ren", "haruto", "minato", "itsuki", "yuma", "yota", "sota", "yuito",
    "yamato", "kenta", "takumi", "naoki", "daisuke", "tsubasa", "makoto", "kazuya", "tatsuya",
    "hiroshi", "kenichi", "takashi", "manabu", "osamu", "minoru", "tsuyoshi", "ichiro", "taro",
    "jiro", "kenji", "yuichi", "ryo", "ryosuke", "kosuke", "yuta", "sho", "kaito", "yuto",
    "haruto", "haru", "hina", "yui", "aoi", "rin", "yuna", "mei", "riko", "misaki", "sakura", "ai",
    "hanako", "yuko", "megumi", "yoko", "naomi", "kumiko", "yumi", "mayumi", "akemi", "tomoko",
    "kyoko", "hiroko", "sachiko", "yuuko", "miho", "aya", "mai", "mai", "kaori", "saori", "nana",
    "chihiro", "aiko", "mizuki", "nanami", "haruka", "kaede", "an", "tsumugi", "mio", "koharu",
    "miyu", "ayaka", "nanako", "mao", "chinatsu", "miku", "sakurako", "kotone", "shiori",
];

static CITIES: &[&str] = &[
    "横浜市", "大阪市", "名古屋市", "札幌市", "福岡市", "川崎市", "神戸市", "京都市", "さいたま市", "広島市", "仙台市", "千葉市", "北九州市",
    "堺市", "浜松市", "新潟市", "熊本市", "相模原市", "岡山市", "静岡市", "船橋市", "鹿児島市", "川口市", "八王子市", "姫路市", "宇都宮市",
    "松山市", "東大阪市", "西宮市", "倉敷市", "市川市", "大分市", "金沢市", "福山市", "尼崎市", "長崎市", "町田市", "豊田市", "高松市",
    "富山市", "岐阜市", "藤沢市", "枚方市", "柏市", "豊中市", "長野市", "一宮市", "和歌山市", "岡崎市", "奈良市", "高槻市", "旭川市",
    "那覇市", "青森市", "盛岡市", "秋田市", "山形市", "福島市", "水戸市", "前橋市", "甲府市", "津市", "大津市", "鳥取市", "松江市", "山口市",
    "徳島市", "高知市", "佐賀市", "宮崎市", "千代田区", "中央区", "港区", "新宿区", "渋谷区", "世田谷区", "品川区", "目黒区", "豊島区",
    "練馬区",
];

static PREFECTURES: &[&str] = &[
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都",
    "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府",
    "大阪府", "兵庫県", "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県",
    "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
];

static TOWNS: &[&str] = &[
    "本町", "中央", "栄町", "緑町", "旭町", "幸町", "寿町", "昭和町", "新町", "元町", "大手町", "丸の内", "西新宿", "道玄坂", "銀座",
    "日本橋", "神田", "赤坂", "六本木", "麻布", "青山", "恵比寿", "中目黒", "自由が丘", "吉祥寺", "梅田", "難波", "心斎橋", "天神",
    "博多", "栄", "錦", "大通西", "桜木町", "若葉", "松原", "東町", "西町", "南町", "北町", "平和町", "富士見町", "宮前", "青葉台",
    "光が丘", "桜ヶ丘", "港南", "山手町",
];

static JOB_TITLES: &[&str] = &[
    "ソフトウェアエンジニア", "プロジェクトマネージャー", "営業", "経理", "看護師", "医師", "弁護士", "建築士", "教師", "薬剤師", "公務員", "会社員",
    "デザイナー", "データサイエンティスト", "システムエンジニア", "販売員", "調理師", "美容師", "保育士", "介護福祉士", "税理士", "公認会計士", "記者",
    "編集者", "翻訳者", "研究員", "技術者", "事務職", "人事担当", "マーケティング担当", "コンサルタント", "銀行員", "警察官", "消防士", "パイロット",
    "運転手", "店長", "代表取締役", "部長", "課長",
];

static WORDS: &[&str] = &[
    "日本", "東京", "会社", "仕事", "時間", "今日", "明日", "世界", "人生", "学校", "先生", "学生", "友達", "家族", "電話", "天気",
    "季節", "春", "夏", "秋", "冬", "桜", "山", "川", "海", "空", "雨", "雪", "花", "木", "森", "道", "町", "駅", "電車",
    "自転車", "料理", "食事", "映画", "音楽", "写真", "旅行", "計画", "問題", "答え", "意見", "経験", "文化", "歴史", "未来", "技術",
    "情報", "社会", "経済", "自然", "環境", "健康", "生活", "気持ち", "言葉", "新しい", "古い", "大きい", "小さい", "美しい", "楽しい",
    "忙しい", "静か", "便利", "大切", "簡単", "毎日", "一緒に", "とても", "すこし", "もっと", "いつも", "行く", "来る", "見る", "聞く",
    "話す", "読む", "書く", "食べる", "飲む", "作る", "考える", "働く",
];
