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
                 ' href="' + esc(item.href) + '">' + item.label + '</a>';
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
