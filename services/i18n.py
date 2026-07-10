"""
Lightweight, dependency-free internationalisation.

English is the source language; templates call `_("English string")`. For a
non-English locale we look the string up in TRANSLATIONS and fall back to the
English source if there's no entry yet — so untranslated strings degrade
gracefully instead of showing blank or a key.

Locale resolution order: explicit choice in the session (set via /set-lang),
then the browser's Accept-Language, then English. Chosen because it needs no
gettext/.po build step — it just works on any deploy.

Bosnian was written to the best of the author's ability and is a good-faith
translation; a native pass can refine it later without touching any template.
"""

from flask import session, request, has_request_context

LANGUAGES = {
    "en": {"label": "English",  "flag": "\U0001F1EC\U0001F1E7"},   # 🇬🇧
    "bs": {"label": "Bosanski", "flag": "\U0001F1E7\U0001F1E6"},   # 🇧🇦
    "tr": {"label": "Türkçe",   "flag": "\U0001F1F9\U0001F1F7"},   # 🇹🇷
}
DEFAULT_LANGUAGE = "en"

TRANSLATIONS = {
    "tr": {
        # ── Sidebar / navigation ──
        "Dashboard": "Panel",
        "Browse Projects": "Projelere Göz At",
        "Community": "Topluluk",
        "Voice Chat": "Sesli Sohbet",
        "AI Assistant": "Yapay Zekâ Asistanı",
        "Post a Project": "Proje Paylaş",
        "My Projects": "Projelerim",
        "My Profile": "Profilim",
        "Support Chat": "Destek Sohbeti",
        "Report Issue": "Sorun Bildir",
        "Admin Panel": "Yönetici Paneli",
        "Light": "Açık",
        "Dark": "Koyu",
        "Log Out": "Çıkış Yap",
        "Notifications": "Bildirimler",
        # ── Auth ──
        "Log In": "Giriş Yap",
        "Create Account": "Hesap Oluştur",
        "Welcome back": "Tekrar hoş geldin",
        "Sign in to your ProjectBuddy account": "ProjectBuddy hesabına giriş yap",
        "University Email": "Üniversite E-postası",
        "Password": "Şifre",
        "Enter your password": "Şifreni gir",
        "Forgot password?": "Şifreni mi unuttun?",
        "Sign In": "Giriş Yap",
        "or": "veya",
        "Continue with GitHub": "GitHub ile Devam Et",
        "Don't have an account?": "Hesabın yok mu?",
        "Create one": "Bir tane oluştur",
        "Admin Login": "Yönetici Girişi",
        "Create account": "Hesap oluştur",
        "First Name": "Ad",
        "Last Name": "Soyad",
        "Department": "Bölüm",
        "Continue": "Devam Et",
        "Back": "Geri",
        "Pick your interests": "İlgi alanlarını seç",
        "You have been logged out.": "Çıkış yaptın.",
        # ── Landing ──
        "Sign In / Register": "Giriş / Kayıt",
        "Get Started": "Başla",
        "Start Matching": "Eşleşmeye Başla",
        "Build something": "Bir şeyler inşa et",
        "great together.": "birlikte, harika.",
        "Find": "Bul", "Match": "Eşleş", "Build": "İnşa Et", "Ship": "Yayınla",
        "Home": "Ana Sayfa", "Platform": "Platform", "Demo": "Demo", "Roles": "Roller",
        "Now live for all universities": "Artık tüm üniversitelerde",
        # hero headline (three lines): "Rastgele takım arkadaşına razı olma."
        "Stop settling for": "Rastgele takım",
        "random": "arkadaşına",
        "teammates.": "razı olma.",
        "ProjectBuddy connects students and instructors through skills, interests, and real collaboration history — so every project starts with the right team.":
            "ProjectBuddy öğrencileri ve eğitmenleri becerilere, ilgi alanlarına ve gerçek işbirliği geçmişine göre buluşturur — böylece her proje doğru ekiple başlar.",
        "Students & Growing": "Öğrenci ve artıyor",
        "Active Projects": "Aktif Proje",
        "Avg. Match Fit": "Ort. Eşleşme",
        "To Find a Team": "Ekip Bulmak",
        # ── Common ──
        "Save": "Kaydet",
        "Cancel": "İptal",
        "Delete": "Sil",
        "Edit Profile": "Profili Düzenle",
        "Send": "Gönder",
        "Apply": "Başvur",
        # ── Landing: feature spotlight ──
        "Don't miss these": "Bunları kaçırma",
        "You had": "Elinde", "superpowers.": "süper güçler vardı.", "Now you know.": "Artık biliyorsun.",
        "Voice rooms, file sharing, study groups — and now full live collaboration with video, screen sharing and shared notes. All built in. Zero setup, zero extras, zero excuses.":
            "Sesli odalar, dosya paylaşımı, çalışma grupları — ve artık video, ekran paylaşımı ve ortak notlarla tam canlı işbirliği. Hepsi dahili. Sıfır kurulum, sıfır ekstra, sıfır bahane.",
        "Feature": "Özellik", "New": "Yeni",
        "Voice Rooms": "Sesli Odalar",
        "Real-time voice built right into your project. No Zoom links, no Discord invites, no third-party apps — just click and talk with your team.":
            "Projenin içine gömülü gerçek zamanlı ses. Zoom linki yok, Discord daveti yok, üçüncü parti uygulama yok — sadece tıkla ve ekibinle konuş.",
        "In-app": "Uygulama içi", "Zero setup": "Sıfır kurulum", "Video ready": "Video hazır",
        "File Sharing": "Dosya Paylaşımı",
        "Share PDFs, images, datasets — directly inside your project. No external links needed. Files live exactly where your team communicates.":
            "PDF'leri, görselleri, veri setlerini — doğrudan projenin içinde paylaş. Harici link gerekmez. Dosyalar ekibinin konuştuğu yerde durur.",
        "All formats": "Tüm formatlar", "Drag & drop": "Sürükle bırak", "Instant share": "Anında paylaş",
        "Study Groups": "Çalışma Grupları",
        "Create or join topic-based study groups with voice chat, text messaging, file sharing, and session scheduling — all in one focused space.":
            "Sesli sohbet, yazışma, dosya paylaşımı ve oturum planlamasıyla konu bazlı çalışma grupları oluştur ya da katıl — hepsi tek bir odakta.",
        "Voice + Chat": "Ses + Sohbet", "Create & join": "Oluştur & katıl", "Schedule": "Planla",
        # ── Landing: collab showcase ──
        "Just shipped": "Yeni yayında", "One room.": "Tek oda.", "Voice, video, screen & notes.": "Ses, video, ekran & not.",
        "Turn any study group into a live workspace: talk, turn on cameras, present your screen, and take notes together — everyone sees every keystroke, live. No Zoom, no Google Docs, no tab-juggling.":
            "Herhangi bir çalışma grubunu canlı çalışma alanına çevir: konuş, kameraları aç, ekranını sun ve birlikte not al — herkes her tuş vuruşunu canlı görür. Zoom yok, Google Docs yok, sekme cambazlığı yok.",
        "Video calls": "Görüntülü arama", "Screen sharing": "Ekran paylaşımı",
        "Live shared notes": "Canlı ortak not", "Zero installs": "Sıfır kurulum", "Open a Live Room": "Canlı Oda Aç",
        # ── Landing: ML section ──
        "Under the hood · Machine learning": "Kaputun altında · Makine öğrenmesi",
        "Your matches are": "Eşleşmelerin", "trained": "eğitildi", "not guessed.": "tahmin değil.",
        "Most platforms match on keywords. ProjectBuddy learns from what actually works — who joined and thrived on which teams — with a real model that ranks every open project by predicted fit, and retrains as the community grows.":
            "Çoğu platform anahtar kelimeye göre eşleştirir. ProjectBuddy gerçekten işe yarayanı öğrenir — kim hangi ekibe katıldı ve başarılı oldu — her açık projeyi tahmini uyuma göre sıralayan gerçek bir modelle, ve topluluk büyüdükçe yeniden eğitilir.",
        "measured with leakage-free cross-validation": "sızıntısız çapraz doğrulamayla ölçüldü",
        "Two towers": "İki kule",
        "your profile and every project embedded into one semantic space": "profilin ve her proje tek bir anlamsal uzaya gömülü",
        "Benchmarked honestly": "Dürüstçe kıyaslandı",
        "against a rule-based baseline, not just shipped on faith": "kurallı bir temele karşı, körü körüne değil",
        "See the model card": "Model kartını gör",
        # ── Landing: manifesto / stats / platform ──
        "Our belief": "İnancımız",
        "We've taken the best elements of team matching and reprogrammed them for the university project world.":
            "Ekip eşleştirmenin en iyi öğelerini alıp üniversite proje dünyası için yeniden programladık.",
        "User Roles": "Kullanıcı Rolü",
        "The Platform": "Platform", "Built for how": "Ekiplerin gerçekte", "teams actually work.": "nasıl çalıştığına göre.",
        "Skill-based matching, reputation systems, course integration — all in one seamless place.":
            "Beceri bazlı eşleştirme, itibar sistemi, ders entegrasyonu — hepsi tek ve kusursuz bir yerde.",
        "Skill-Based Matching": "Beceri Bazlı Eşleştirme",
        "Personalized recommendations powered by your 5 interest tags. No more scrolling through irrelevant listings.":
            "5 ilgi etiketinle güçlenen kişisel öneriler. Alakasız ilanlarda gezinmek yok.",
        "Reputation System": "İtibar Sistemi",
        "Build a verifiable track record with peer ratings, skill endorsements, and achievement badges that mean something.":
            "Akran puanları, beceri onayları ve gerçekten anlam taşıyan başarı rozetleriyle doğrulanabilir bir geçmiş oluştur.",
        "Course Integration": "Ders Entegrasyonu",
        "Instructors post course-specific projects. Only enrolled students can apply. Everything stays organized.":
            "Eğitmenler derse özel projeler yayınlar. Sadece kayıtlı öğrenciler başvurabilir. Her şey düzenli kalır.",
        "Trust & Safety": "Güven & Güvenlik",
        "Built-in reporting system. Admins can warn, suspend, or ban users to keep the community clean.":
            "Dahili raporlama sistemi. Yöneticiler topluluğu temiz tutmak için uyarabilir, askıya alabilir veya yasaklayabilir.",
        "Application Flow": "Başvuru Akışı",
        "Apply, accept, manage your team — all from a clean dashboard. No awkward cold messages.":
            "Başvur, kabul et, ekibini yönet — hepsi temiz bir panelden. Garip soğuk mesajlar yok.",
        "Achievement Badges": "Başarı Rozetleri",
        "First Step after 1 project. Veteran after 5. Expert after 10 endorsements. Progress that matters.":
            "1 projeden sonra İlk Adım. 5'ten sonra Kıdemli. 10 onaydan sonra Uzman. Anlamlı ilerleme.",
        "Live Collab Rooms": "Canlı İşbirliği Odaları",
        "Voice, cameras, screen sharing and live shared notes in every study group. One click, zero installs.":
            "Her çalışma grubunda ses, kamera, ekran paylaşımı ve canlı ortak not. Tek tık, sıfır kurulum.",
        # ── Landing: demo / roles ──
        "See it in action": "İş başında gör", "Watch ProjectBuddy": "ProjectBuddy'yi izle", "work for you": "senin için çalışırken",
        "Who it's for": "Kimler için", "Three roles,": "Üç rol,", "one platform.": "tek platform.",
        "Every account type gets a purpose-built toolkit. No bloat, no confusion — just what each person needs.":
            "Her hesap türü amaca özel bir araç setine sahip. Şişkinlik yok, kafa karışıklığı yok — herkesin ihtiyacı olan kadar.",
        "Role": "Rol", "Student": "Öğrenci",
        "The core experience. Post projects, browse listings, apply to teams, and grow a reputation that follows you.":
            "Ana deneyim. Proje paylaş, ilanlara göz at, ekiplere başvur ve seni takip eden bir itibar oluştur.",
        "Post & browse projects": "Proje paylaş & göz at", "Apply to teams in one click": "Tek tıkla ekiplere başvur",
        "Earn badges & endorsements": "Rozet & onay kazan", "5-tag interest matching": "5 etiketli ilgi eşleşmesi",
        "Most Users": "Çoğu Kullanıcı", "Instructor": "Eğitmen",
        "Run projects as part of a course. Tie listings to enrollment, manage applicants, and rate contributions.":
            "Projeleri dersin bir parçası olarak yürüt. İlanları kayda bağla, başvuranları yönet ve katkıları puanla.",
        "Course-tied project posts": "Derse bağlı proje ilanları", "Manage applications": "Başvuruları yönet",
        "Set deadlines & scope": "Son tarih & kapsam belirle", "Rate team members": "Ekip üyelerini puanla",
        "Faculty": "Öğretim Üyesi", "Admin": "Yönetici",
        "Keep the community healthy. Review reports, act on violations, and watch platform-wide activity.":
            "Topluluğu sağlıklı tut. Raporları incele, ihlallere karşı harekete geç ve platform genelindeki etkinliği izle.",
        "Review user reports": "Kullanıcı raporlarını incele", "Issue warnings & bans": "Uyarı & yasak ver",
        "Monitor activity": "Etkinliği izle", "Moderate content": "İçeriği denetle", "Moderation": "Denetim",
        # ── Landing: CTA / footer ──
        "Get started today": "Bugün başla", "Ready to find your": "Hayalindeki ekibi", "dream team?": "bulmaya hazır mısın?",
        "Create Your Profile": "Profilini Oluştur", "Explore Projects": "Projeleri Keşfet",
        "Free for students": "Öğrenciler için ücretsiz", "No credit card": "Kredi kartı yok", "Set up in 2 minutes": "2 dakikada kurulum",
        '"We matched our entire 6-person team in under 48 hours. Nothing else comes close."':
            '"6 kişilik ekibimizin tamamını 48 saatten kısa sürede eşleştirdik. Hiçbir şey buna yaklaşamaz."',
        '"The voice rooms changed everything. We used to schedule Zooms — now we just jump in."':
            '"Sesli odalar her şeyi değiştirdi. Eskiden Zoom ayarlardık — şimdi direkt giriyoruz."',
        '"Posted my project, got 4 qualified applicants by morning. The matching is genuinely good."':
            '"Projemi paylaştım, sabaha 4 nitelikli başvuru geldi. Eşleştirme gerçekten iyi."',
        "Privacy": "Gizlilik", "Terms": "Koşullar", "Contact": "İletişim",
    },
    "bs": {
        # ── Sidebar / navigation ──
        "Dashboard": "Nadzorna ploča",
        "Browse Projects": "Pregledaj projekte",
        "Community": "Zajednica",
        "Voice Chat": "Glasovni chat",
        "AI Assistant": "AI asistent",
        "Post a Project": "Objavi projekat",
        "My Projects": "Moji projekti",
        "My Profile": "Moj profil",
        "Support Chat": "Podrška",
        "Report Issue": "Prijavi problem",
        "Admin Panel": "Admin panel",
        "Light": "Svijetlo",
        "Dark": "Tamno",
        "Log Out": "Odjava",
        "Notifications": "Obavijesti",
        # ── Auth ──
        "Log In": "Prijava",
        "Create Account": "Napravi nalog",
        "Welcome back": "Dobro došli nazad",
        "Sign in to your ProjectBuddy account": "Prijavite se na svoj ProjectBuddy nalog",
        "University Email": "Univerzitetski e-mail",
        "Password": "Lozinka",
        "Enter your password": "Unesite lozinku",
        "Forgot password?": "Zaboravili ste lozinku?",
        "Sign In": "Prijavi se",
        "or": "ili",
        "Continue with GitHub": "Nastavi sa GitHub-om",
        "Don't have an account?": "Nemate nalog?",
        "Create one": "Napravite ga",
        "Admin Login": "Admin prijava",
        "Create account": "Napravi nalog",
        "First Name": "Ime",
        "Last Name": "Prezime",
        "Department": "Odsjek",
        "Continue": "Nastavi",
        "Back": "Nazad",
        "Pick your interests": "Odaberite interese",
        "You have been logged out.": "Odjavljeni ste.",
        # ── Landing ──
        "Sign In / Register": "Prijava / Registracija",
        "Get Started": "Započni",
        "Start Matching": "Počni povezivanje",
        "Build something": "Napravi nešto",
        "great together.": "sjajno, zajedno.",
        "Find": "Nađi", "Match": "Poveži", "Build": "Gradi", "Ship": "Objavi",
        "Home": "Početna", "Platform": "Platforma", "Demo": "Demo", "Roles": "Uloge",
        "Now live for all universities": "Sada dostupno za sve univerzitete",
        # hero headline (three lines): "Prestani birati nasumične saigrače."
        "Stop settling for": "Prestani birati",
        "random": "nasumične",
        "teammates.": "saigrače.",
        "ProjectBuddy connects students and instructors through skills, interests, and real collaboration history — so every project starts with the right team.":
            "ProjectBuddy povezuje studente i profesore na osnovu vještina, interesa i stvarne historije saradnje — tako da svaki projekat počinje s pravim timom.",
        "Students & Growing": "Studenata i raste",
        "Active Projects": "Aktivni projekti",
        "Avg. Match Fit": "Prosj. podudarnost",
        "To Find a Team": "Za pronalazak tima",
        # ── Common ──
        "Save": "Sačuvaj",
        "Cancel": "Otkaži",
        "Delete": "Obriši",
        "Edit Profile": "Uredi profil",
        "Send": "Pošalji",
        "Apply": "Prijavi se",
        # ── Landing: feature spotlight ──
        "Don't miss these": "Ne propustite ovo",
        "You had": "Imali ste", "superpowers.": "supermoći.", "Now you know.": "Sad znate.",
        "Voice rooms, file sharing, study groups — and now full live collaboration with video, screen sharing and shared notes. All built in. Zero setup, zero extras, zero excuses.":
            "Glasovne sobe, dijeljenje datoteka, studijske grupe — a sada i potpuna live saradnja s videom, dijeljenjem ekrana i zajedničkim bilješkama. Sve ugrađeno. Bez postavljanja, bez dodataka, bez izgovora.",
        "Feature": "Funkcija", "New": "Novo",
        "Voice Rooms": "Glasovne sobe",
        "Real-time voice built right into your project. No Zoom links, no Discord invites, no third-party apps — just click and talk with your team.":
            "Glasovni razgovor u realnom vremenu, ugrađen u vaš projekat. Bez Zoom linkova, bez Discord poziva, bez aplikacija trećih strana — samo kliknite i razgovarajte s timom.",
        "In-app": "U aplikaciji", "Zero setup": "Bez postavljanja", "Video ready": "Spremno za video",
        "File Sharing": "Dijeljenje datoteka",
        "Share PDFs, images, datasets — directly inside your project. No external links needed. Files live exactly where your team communicates.":
            "Dijelite PDF-ove, slike, skupove podataka — direktno unutar projekta. Bez vanjskih linkova. Datoteke su tačno tamo gdje tim komunicira.",
        "All formats": "Svi formati", "Drag & drop": "Povuci i pusti", "Instant share": "Trenutno dijeljenje",
        "Study Groups": "Studijske grupe",
        "Create or join topic-based study groups with voice chat, text messaging, file sharing, and session scheduling — all in one focused space.":
            "Napravite ili se pridružite studijskim grupama po temama uz glasovni chat, poruke, dijeljenje datoteka i zakazivanje sesija — sve u jednom fokusiranom prostoru.",
        "Voice + Chat": "Glas + Chat", "Create & join": "Napravi i pridruži se", "Schedule": "Zakaži",
        # ── Landing: collab showcase ──
        "Just shipped": "Upravo objavljeno", "One room.": "Jedna soba.", "Voice, video, screen & notes.": "Glas, video, ekran i bilješke.",
        "Turn any study group into a live workspace: talk, turn on cameras, present your screen, and take notes together — everyone sees every keystroke, live. No Zoom, no Google Docs, no tab-juggling.":
            "Pretvorite bilo koju studijsku grupu u živi radni prostor: pričajte, uključite kamere, prikažite ekran i zajedno vodite bilješke — svako vidi svaki pritisak tipke, uživo. Bez Zoom-a, bez Google Docs-a, bez žongliranja tabovima.",
        "Video calls": "Video pozivi", "Screen sharing": "Dijeljenje ekrana",
        "Live shared notes": "Žive zajedničke bilješke", "Zero installs": "Bez instalacija", "Open a Live Room": "Otvori živu sobu",
        # ── Landing: ML section ──
        "Under the hood · Machine learning": "Ispod haube · Mašinsko učenje",
        "Your matches are": "Vaša poklapanja su", "trained": "trenirana", "not guessed.": "ne pogađana.",
        "Most platforms match on keywords. ProjectBuddy learns from what actually works — who joined and thrived on which teams — with a real model that ranks every open project by predicted fit, and retrains as the community grows.":
            "Većina platformi povezuje po ključnim riječima. ProjectBuddy uči iz onoga što stvarno funkcioniše — ko se pridružio i uspio u kojim timovima — pravim modelom koji rangira svaki otvoreni projekat po predviđenom poklapanju, i ponovo se trenira kako zajednica raste.",
        "measured with leakage-free cross-validation": "mjereno unakrsnom validacijom bez curenja",
        "Two towers": "Dvije kule",
        "your profile and every project embedded into one semantic space": "vaš profil i svaki projekat ugrađeni u jedan semantički prostor",
        "Benchmarked honestly": "Pošteno upoređeno",
        "against a rule-based baseline, not just shipped on faith": "s osnovnim modelom po pravilima, a ne objavljeno naslijepo",
        "See the model card": "Pogledaj karticu modela",
        # ── Landing: manifesto / stats / platform ──
        "Our belief": "Naše uvjerenje",
        "We've taken the best elements of team matching and reprogrammed them for the university project world.":
            "Uzeli smo najbolje elemente povezivanja timova i preprogramirali ih za svijet univerzitetskih projekata.",
        "User Roles": "Korisničke uloge",
        "The Platform": "Platforma", "Built for how": "Napravljeno za to kako", "teams actually work.": "timovi stvarno rade.",
        "Skill-based matching, reputation systems, course integration — all in one seamless place.":
            "Povezivanje po vještinama, sistem reputacije, integracija predmeta — sve na jednom besprijekornom mjestu.",
        "Skill-Based Matching": "Povezivanje po vještinama",
        "Personalized recommendations powered by your 5 interest tags. No more scrolling through irrelevant listings.":
            "Personalizirane preporuke na osnovu vaših 5 oznaka interesa. Nema više prelistavanja nebitnih oglasa.",
        "Reputation System": "Sistem reputacije",
        "Build a verifiable track record with peer ratings, skill endorsements, and achievement badges that mean something.":
            "Izgradite provjerljivu evidenciju uz ocjene kolega, potvrde vještina i značke postignuća koje nešto znače.",
        "Course Integration": "Integracija predmeta",
        "Instructors post course-specific projects. Only enrolled students can apply. Everything stays organized.":
            "Profesori objavljuju projekte vezane za predmet. Samo upisani studenti mogu se prijaviti. Sve ostaje organizovano.",
        "Trust & Safety": "Povjerenje i sigurnost",
        "Built-in reporting system. Admins can warn, suspend, or ban users to keep the community clean.":
            "Ugrađen sistem prijava. Administratori mogu upozoriti, suspendovati ili blokirati korisnike da zajednica ostane čista.",
        "Application Flow": "Tok prijava",
        "Apply, accept, manage your team — all from a clean dashboard. No awkward cold messages.":
            "Prijavite se, prihvatite, upravljajte timom — sve s jedne uredne kontrolne ploče. Bez neugodnih hladnih poruka.",
        "Achievement Badges": "Značke postignuća",
        "First Step after 1 project. Veteran after 5. Expert after 10 endorsements. Progress that matters.":
            "Prvi korak nakon 1 projekta. Veteran nakon 5. Stručnjak nakon 10 potvrda. Napredak koji je bitan.",
        "Live Collab Rooms": "Žive sobe za saradnju",
        "Voice, cameras, screen sharing and live shared notes in every study group. One click, zero installs.":
            "Glas, kamere, dijeljenje ekrana i žive zajedničke bilješke u svakoj studijskoj grupi. Jedan klik, bez instalacija.",
        # ── Landing: demo / roles ──
        "See it in action": "Pogledaj na djelu", "Watch ProjectBuddy": "Gledaj ProjectBuddy", "work for you": "kako radi za tebe",
        "Who it's for": "Za koga je", "Three roles,": "Tri uloge,", "one platform.": "jedna platforma.",
        "Every account type gets a purpose-built toolkit. No bloat, no confusion — just what each person needs.":
            "Svaki tip naloga dobija namjenski set alata. Bez viška, bez zabune — samo ono što svakome treba.",
        "Role": "Uloga", "Student": "Student",
        "The core experience. Post projects, browse listings, apply to teams, and grow a reputation that follows you.":
            "Osnovno iskustvo. Objavljujte projekte, pregledajte oglase, prijavljujte se u timove i gradite reputaciju koja vas prati.",
        "Post & browse projects": "Objavi i pregledaj projekte", "Apply to teams in one click": "Prijavi se u timove jednim klikom",
        "Earn badges & endorsements": "Osvoji značke i potvrde", "5-tag interest matching": "Povezivanje po 5 interesa",
        "Most Users": "Većina korisnika", "Instructor": "Profesor",
        "Run projects as part of a course. Tie listings to enrollment, manage applicants, and rate contributions.":
            "Vodite projekte kao dio predmeta. Povežite oglase s upisom, upravljajte prijavama i ocjenjujte doprinose.",
        "Course-tied project posts": "Projekti vezani za predmet", "Manage applications": "Upravljaj prijavama",
        "Set deadlines & scope": "Postavi rokove i obim", "Rate team members": "Ocijeni članove tima",
        "Faculty": "Nastavno osoblje", "Admin": "Administrator",
        "Keep the community healthy. Review reports, act on violations, and watch platform-wide activity.":
            "Održavajte zajednicu zdravom. Pregledajte prijave, reagujte na prekršaje i pratite aktivnost cijele platforme.",
        "Review user reports": "Pregledaj prijave korisnika", "Issue warnings & bans": "Izdaj upozorenja i blokade",
        "Monitor activity": "Prati aktivnost", "Moderate content": "Moderiraj sadržaj", "Moderation": "Moderacija",
        # ── Landing: CTA / footer ──
        "Get started today": "Započni danas", "Ready to find your": "Spreman/na da nađeš", "dream team?": "tim iz snova?",
        "Create Your Profile": "Napravi profil", "Explore Projects": "Istraži projekte",
        "Free for students": "Besplatno za studente", "No credit card": "Bez kreditne kartice", "Set up in 2 minutes": "Postavljanje za 2 minute",
        '"We matched our entire 6-person team in under 48 hours. Nothing else comes close."':
            '"Povezali smo cijeli tim od 6 ljudi za manje od 48 sati. Ništa se ne može mjeriti s tim."',
        '"The voice rooms changed everything. We used to schedule Zooms — now we just jump in."':
            '"Glasovne sobe su promijenile sve. Ranije smo zakazivali Zoom — sad se samo ubacimo."',
        '"Posted my project, got 4 qualified applicants by morning. The matching is genuinely good."':
            '"Objavio sam projekat, do jutra dobio 4 kvalifikovana kandidata. Povezivanje je stvarno dobro."',
        "Privacy": "Privatnost", "Terms": "Uslovi", "Contact": "Kontakt",
    },
}


def get_locale():
    """Resolve the active language code (en / bs / tr)."""
    if has_request_context():
        chosen = session.get("lang")
        if chosen in LANGUAGES:
            return chosen
        best = request.accept_languages.best_match(list(LANGUAGES.keys()))
        if best:
            return best
    return DEFAULT_LANGUAGE


def translate(text, **kwargs):
    """Translate `text` into the active locale, falling back to English."""
    loc = get_locale()
    out = TRANSLATIONS.get(loc, {}).get(text, text)
    if kwargs:
        try:
            out = out.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return out
