/**
 * site-chrome.js — Injects the shared site navigation into hub pages.
 * Compatible with Chrome, Firefox, Safari 9+, Edge, IE 11.
 *
 * Configure each page via <meta> tags in <head>:
 *
 *   <!-- Required: path to the site root's index.html from this page.
 *        Every nav link (Projects, Walkthroughs, About) is worked out from it. -->
 *   <meta name="sc-portal" content="../../index.html">
 *
 *   <!-- Hub/index pages: nav sits inside .panel above the hero -->
 *   <meta name="sc-type" content="hub">
 *
 *   <!-- Optional: highlight the current section
 *        (home | projects | walkthroughs | about) -->
 *   <meta name="sc-active" content="projects">
 *
 *   <!-- Optional: extra link after the main nav, e.g. a project's own index -->
 *   <meta name="sc-platidx-href"  content="./index.html">
 *   <meta name="sc-platidx-label" content="Packer Pipeline">
 *
 *   <!-- Sub-pages only: fixed header bar with site name + page title -->
 *   <meta name="sc-logo" content="../../assets/logo.svg">
 *   <meta name="sc-site" content="Portfolio Site">
 *   <meta name="sc-page" content="Overview">
 *
 * Injected structure (prepended to <body>, or into .panel on hub pages):
 *   1. .site-header   (sub-pages only, when sc-site + sc-page are present)
 *   2. .plat-nav      (always; class .plat-nav--hub or .plat-nav--sub)
 */
(function () {
    'use strict';

    function getMeta(name) {
        var el = document.querySelector('meta[name="' + name + '"]');
        return el ? el.getAttribute('content') : null;
    }

    /* ── Read config from <meta> tags ──────────────────────── */
    var portalHref   = getMeta('sc-portal')         || '../../index.html';
    var logoSrc      = getMeta('sc-logo')           || '';
    var siteName     = getMeta('sc-site')           || '';
    var pageName     = getMeta('sc-page')           || '';
    var platIdxHref  = getMeta('sc-platidx-href')   || '';
    var platIdxLabel = getMeta('sc-platidx-label')  || '';
    var active       = getMeta('sc-active')         || '';
    var pageType     = getMeta('sc-type')           || 'sub';

    var root      = portalHref.replace(/index\.html$/, '');
    var isSub     = (pageType !== 'hub');
    var hasHeader = isSub && siteName && pageName;

    var NAV = [
        { id: 'home',         label: 'Home',         href: portalHref },
        { id: 'projects',     label: 'Projects',     href: root + 'projects/index.html' },
        { id: 'walkthroughs', label: 'Walkthroughs', href: root + 'walkthroughs/index.html' },
        { id: 'about',        label: 'About',        href: root + 'about/index.html' }
    ];

    function el(tag, cls) {
        var e = document.createElement(tag);
        if (cls) { e.className = cls; }
        return e;
    }

    function esc(s) {
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    /* ── 1. Site header (sub-pages only) ───────────────────── */
    var header = null;
    if (hasHeader) {
        header = el('header', 'site-header');
        header.setAttribute('aria-label', 'Site header');
        var logoStyle = logoSrc ? ' style="background-image:url(\'' + esc(logoSrc) + '\')"' : '';
        header.innerHTML =
            '<div class="site-header__logo" role="img" aria-label="Site logo"' + logoStyle + '></div>' +
            '<div class="site-header__divider"></div>' +
            '<span class="site-header__site">' + esc(siteName) + '</span>' +
            '<span class="site-header__sep">&#8250;</span>' +
            '<span class="site-header__page">' + esc(pageName) + '</span>';
    }

    /* ── 2. Nav bar ────────────────────────────────────────── */
    var nav = el('nav', 'plat-nav ' + (isSub ? 'plat-nav--sub' : 'plat-nav--hub'));
    nav.setAttribute('aria-label', 'Site navigation');

    var links = '';
    for (var i = 0; i < NAV.length; i++) {
        var item = NAV[i];
        var isActive = item.id === active;
        links += '<a class="plat-nav__link' + (isActive ? ' plat-nav__link--active' : '') + '"' +
                 (isActive ? ' aria-current="page"' : '') +
                 ' href="' + esc(item.href) + '" data-i18n="' + item.id + '">' + item.label + '</a>';
    }

    var extra = '';
    if (platIdxHref && platIdxLabel) {
        extra = '<div class="plat-nav__group plat-nav__group--extra">' +
                '<a class="plat-nav__link" href="' + esc(platIdxHref) + '">' + esc(platIdxLabel) + '</a>' +
                '</div>';
    }

    nav.innerHTML = '<div class="plat-nav__group">' + links + '</div>' + extra;

    /* ── Inject ────────────────────────────────────────────── */
    var body  = document.body;
    var first = body.firstChild || null;

    if (!isSub) {
        var panel = document.querySelector('.panel');
        if (panel) {
            panel.insertBefore(nav, panel.firstChild);
        } else {
            body.insertBefore(nav, first);
        }
    } else {
        body.insertBefore(nav, first);
        if (header) { body.insertBefore(header, nav); }
    }



    /* ── Built-in (self-hosted) nav translations; work in every browser ── */
    var UI = {
        vi: { home: 'Trang chủ', projects: 'Dự án', walkthroughs: 'Hướng dẫn', about: 'Giới thiệu' },
        es: { home: 'Inicio', projects: 'Proyectos', walkthroughs: 'Recorridos', about: 'Acerca de' },
        fr: { home: 'Accueil', projects: 'Projets', walkthroughs: 'Présentations', about: 'À propos' },
        de: { home: 'Startseite', projects: 'Projekte', walkthroughs: 'Walkthroughs', about: 'Über mich' },
        it: { home: 'Home', projects: 'Progetti', walkthroughs: 'Presentazioni', about: 'Chi sono' },
        pt: { home: 'Início', projects: 'Projetos', walkthroughs: 'Apresentações', about: 'Sobre' },
        nl: { home: 'Home', projects: 'Projecten', walkthroughs: 'Rondleidingen', about: 'Over mij' },
        sv: { home: 'Hem', projects: 'Projekt', walkthroughs: 'Genomgångar', about: 'Om' },
        pl: { home: 'Strona główna', projects: 'Projekty', walkthroughs: 'Prezentacje', about: 'O mnie' },
        ru: { home: 'Главная', projects: 'Проекты', walkthroughs: 'Обзоры', about: 'Обо мне' },
        uk: { home: 'Головна', projects: 'Проєкти', walkthroughs: 'Огляди', about: 'Про мене' },
        tr: { home: 'Ana sayfa', projects: 'Projeler', walkthroughs: 'Anlatımlar', about: 'Hakkında' },
        ar: { home: 'الرئيسية', projects: 'المشاريع', walkthroughs: 'الشروحات', about: 'نبذة' },
        he: { home: 'בית', projects: 'פרויקטים', walkthroughs: 'הדרכות', about: 'אודות' },
        fa: { home: 'خانه', projects: 'پروژه‌ها', walkthroughs: 'راهنماها', about: 'درباره' },
        hi: { home: 'होम', projects: 'प्रोजेक्ट', walkthroughs: 'वॉकथ्रू', about: 'परिचय' },
        bn: { home: 'হোম', projects: 'প্রকল্প', walkthroughs: 'ওয়াকথ্রু', about: 'পরিচিতি' },
        id: { home: 'Beranda', projects: 'Proyek', walkthroughs: 'Panduan', about: 'Tentang' },
        ms: { home: 'Laman utama', projects: 'Projek', walkthroughs: 'Panduan', about: 'Perihal' },
        tl: { home: 'Home', projects: 'Mga Proyekto', walkthroughs: 'Mga Walkthrough', about: 'Tungkol' },
        th: { home: 'หน้าแรก', projects: 'โปรเจกต์', walkthroughs: 'คำแนะนำ', about: 'เกี่ยวกับ' },
        ja: { home: 'ホーム', projects: 'プロジェクト', walkthroughs: 'ウォークスルー', about: '概要' },
        ko: { home: '홈', projects: '프로젝트', walkthroughs: '워크스루', about: '소개' },
        'zh-CN': { home: '首页', projects: '项目', walkthroughs: '演示', about: '关于' },
        'zh-TW': { home: '首頁', projects: '專案', walkthroughs: '簡報', about: '關於' },
        el: { home: 'Αρχική', projects: 'Έργα', walkthroughs: 'Παρουσιάσεις', about: 'Σχετικά' },
        cs: { home: 'Domů', projects: 'Projekty', walkthroughs: 'Prezentace', about: 'O mně' },
        ro: { home: 'Acasă', projects: 'Proiecte', walkthroughs: 'Prezentări', about: 'Despre' },
        hu: { home: 'Kezdőlap', projects: 'Projektek', walkthroughs: 'Bemutatók', about: 'Rólam' },
        da: { home: 'Hjem', projects: 'Projekter', walkthroughs: 'Gennemgange', about: 'Om' },
        fi: { home: 'Etusivu', projects: 'Projektit', walkthroughs: 'Esittelyt', about: 'Tietoja' },
        no: { home: 'Hjem', projects: 'Prosjekter', walkthroughs: 'Gjennomganger', about: 'Om' },
        sw: { home: 'Mwanzo', projects: 'Miradi', walkthroughs: 'Maelekezo', about: 'Kuhusu' }
    };
    var RTL = { ar: 1, he: 1, fa: 1, ur: 1, ps: 1, sd: 1, ug: 1, yi: 1 };

    function applyUI(lang) {
        var dict = UI[lang] || null;
        var anchors = nav.querySelectorAll('[data-i18n]');
        for (var a = 0; a < anchors.length; a++) {
            var id = anchors[a].getAttribute('data-i18n');
            var base = '';
            for (var n = 0; n < NAV.length; n++) { if (NAV[n].id === id) { base = NAV[n].label; } }
            anchors[a].textContent = dict ? dict[id] : base;
        }
        document.documentElement.setAttribute('lang', lang || 'en');
        document.documentElement.setAttribute('dir', RTL[lang] ? 'rtl' : 'ltr');
    }
    function storedLang() {
        try { return localStorage.getItem('sc-lang') || ''; } catch (e) { return ''; }
    }
    function storeLang(l) {
        try { if (l) { localStorage.setItem('sc-lang', l); } else { localStorage.removeItem('sc-lang'); } } catch (e) { /* private mode */ }
    }

    /* ── Language picker (Google Website Translate, loaded on demand) ── */
    var LANGS = 'af:Afrikaans,sq:Shqip,am:አማርኛ,ar:العربية,hy:Հայերեն,az:Azərbaycan,eu:Euskara,be:Беларуская,bn:বাংলা,bs:Bosanski,bg:Български,ca:Català,ceb:Cebuano,zh-CN:中文 (简体),zh-TW:中文 (繁體),co:Corsu,hr:Hrvatski,cs:Čeština,da:Dansk,nl:Nederlands,eo:Esperanto,et:Eesti,fi:Suomi,fr:Français,fy:Frysk,gl:Galego,ka:ქართული,de:Deutsch,el:Ελληνικά,gu:ગુજરાતી,ht:Kreyòl ayisyen,ha:Hausa,haw:ʻŌlelo Hawaiʻi,he:עברית,hi:हिन्दी,hmn:Hmong,hu:Magyar,is:Íslenska,ig:Igbo,id:Bahasa Indonesia,ga:Gaeilge,it:Italiano,ja:日本語,jv:Basa Jawa,kn:ಕನ್ನಡ,kk:Қазақ,km:ខ្មែរ,rw:Kinyarwanda,ko:한국어,ku:Kurdî,ky:Кыргызча,lo:ລາວ,la:Latina,lv:Latviešu,lt:Lietuvių,lb:Lëtzebuergesch,mk:Македонски,mg:Malagasy,ms:Bahasa Melayu,ml:മലയാളം,mt:Malti,mi:Māori,mr:मराठी,mn:Монгол,my:မြန်မာ,ne:नेपाली,no:Norsk,ny:Chichewa,or:ଓଡ଼ିଆ,ps:پښتو,fa:فارسی,pl:Polski,pt:Português,pa:ਪੰਜਾਬੀ,ro:Română,ru:Русский,sm:Gagana Samoa,gd:Gàidhlig,sr:Српски,st:Sesotho,sn:Shona,sd:سنڌي,si:සිංහල,sk:Slovenčina,sl:Slovenščina,so:Soomaali,es:Español,su:Basa Sunda,sw:Kiswahili,sv:Svenska,tl:Filipino,tg:Тоҷикӣ,ta:தமிழ்,tt:Татар,te:తెలుగు,th:ไทย,tr:Türkçe,tk:Türkmen,uk:Українська,ur:اردو,ug:ئۇيغۇرچە,uz:Oʻzbek,vi:Tiếng Việt,cy:Cymraeg,xh:isiXhosa,yi:ייִדיש,yo:Yorùbá,zu:isiZulu'.split(',');

    function getCookie(name) {
        var m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
        return m ? decodeURIComponent(m[1]) : '';
    }
    function setTransCookie(lang) {
        var host = location.hostname;
        var val = lang ? '/en/' + lang : '';
        var exp = lang ? '' : ';expires=Thu, 01 Jan 1970 00:00:00 GMT';
        var base = 'googtrans=' + val + ';path=/' + exp;
        document.cookie = base;
        if (host.indexOf('.') !== -1) { document.cookie = base + ';domain=' + host; }
    }

    var langWrap = el('div', 'plat-nav__lang');
    var sel = el('select', 'plat-nav__lang-select notranslate');
    sel.setAttribute('aria-label', 'Language');
    sel.setAttribute('translate', 'no');
    var current = storedLang() || (getCookie('googtrans').split('/')[2]) || '';
    var opts = '<option value="">English</option>';
    for (var li = 0; li < LANGS.length; li++) {
        var parts = LANGS[li].split(/:(.+)/);
        opts += '<option value="' + parts[0] + '"' + (parts[0] === current ? ' selected' : '') + '>' +
                esc(parts[1]) + '</option>';
    }
    sel.innerHTML = opts;
    langWrap.appendChild(sel);
    nav.appendChild(langWrap);

    sel.onchange = function () {
        storeLang(sel.value);
        setTransCookie(sel.value);
        applyUI(sel.value);
        location.reload();
    };

    applyUI(current);

    if (current) {
        window.googleTranslateInit = function () {
            new window.google.translate.TranslateElement(
                { pageLanguage: 'en', autoDisplay: false }, 'google_translate_element');
        };
        var holder = el('div');
        holder.id = 'google_translate_element';
        holder.style.display = 'none';
        document.body.appendChild(holder);
        var gs = document.createElement('script');
        gs.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateInit';
        gs.async = true;
        document.body.appendChild(gs);
    }

    /* ── Back-to-top wiring ────────────────────────────────── */
    var btt = document.getElementById('back-to-top');
    if (btt) {
        var passiveOpt = false;
        try {
            var opts = Object.defineProperty({}, 'passive', { get: function () { passiveOpt = true; } });
            window.addEventListener('testPassive', null, opts);
            window.removeEventListener('testPassive', null, opts);
        } catch (e) { /* not supported */ }

        var onScroll = function () {
            var y = window.pageYOffset || document.documentElement.scrollTop || 0;
            if (y > 300) {
                btt.className = btt.className.replace(/\bvisible\b/, '') + ' visible';
            } else {
                btt.className = btt.className.replace(/\s*\bvisible\b/, '');
            }
        };
        window.addEventListener('scroll', onScroll, passiveOpt ? { passive: true } : false);

        btt.onclick = function (e) {
            e.preventDefault();
            if (typeof window.scrollTo === 'function' && 'scrollBehavior' in document.documentElement.style) {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                document.documentElement.scrollTop = 0;
                document.body.scrollTop = 0;
            }
        };
    }
})();
