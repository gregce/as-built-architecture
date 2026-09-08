#!/usr/bin/env python3
"""Read-only, standard-library checks for a standalone architecture explorer.

This inspects HTML structure, explicit JSON sources, and optional browser-exported
hrefs. It does not execute JavaScript, render CSS, or establish architecture truth.
All JSON output is deterministic for unchanged input and local files.
"""

import argparse
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


SCHEMA_VERSION = 1


class InputError(Exception):
    pass


class JSONArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise InputError(message)


def strict_json(value):
    def reject_constant(token):
        raise ValueError("Non-JSON numeric constant: " + token)

    def unique_object(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("Duplicate JSON object key: " + key)
            result[key] = item
        return result

    return json.loads(value, parse_constant=reject_constant, object_pairs_hook=unique_object)


def clean_url(value):
    # Match the browser's removal of ASCII tabs/newlines and boundary controls.
    return value.strip("".join(chr(c) for c in range(33))).replace("\t", "").replace("\r", "").replace("\n", "")


def css_escape(css, index):
    """Read one CSS escape, starting at the backslash."""
    index += 1
    start = index
    while index < len(css) and index - start < 6 and css[index] in "0123456789abcdefABCDEF":
        index += 1
    if index > start:
        code = int(css[start:index], 16)
        value = chr(code) if 0 < code <= 0x10FFFF and not 0xD800 <= code <= 0xDFFF else "\ufffd"
        if index < len(css) and css[index].isspace():
            index += 1
        return value, index
    if index >= len(css):
        return "", index
    if css[index] in "\n\r\f":
        return "", index + 1
    return css[index], index + 1


def css_string(css, index):
    quote = css[index]
    index += 1
    value = []
    while index < len(css):
        if css[index] == quote:
            return "".join(value), index + 1
        if css[index] == "\\":
            char, index = css_escape(css, index)
            value.append(char)
        else:
            value.append(css[index])
            index += 1
    return "".join(value), index


def css_urls(css):
    """Extract actual url() and quoted @import tokens, skipping comments/strings.

    A small lexical scanner, not a CSS validity checker. Escapes are decoded so
    escaped function names cannot silently hide a network dependency.
    """
    found = []
    i = 0
    import_pending = False
    while i < len(css):
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            i = len(css) if end < 0 else end + 2
            continue
        if css[i].isspace():
            i += 1
            continue
        if css[i] in "\"'":
            start = i
            value, i = css_string(css, i)
            if import_pending:
                found.append((value, css.count("\n", 0, start)))
            import_pending = False
            continue
        if css[i].isalpha() or css[i] in "@_-\\":
            start = i
            word = []
            while i < len(css) and (css[i].isalnum() or css[i] in "@_-\\"):
                if css[i] == "\\":
                    char, i = css_escape(css, i)
                    word.append(char)
                else:
                    word.append(css[i])
                    i += 1
            name = "".join(word).lower()
            if name == "@import":
                import_pending = True
                continue
            if name == "url" and i < len(css) and css[i] == "(":
                i += 1
                while i < len(css) and css[i].isspace():
                    i += 1
                if i < len(css) and css[i] in "\"'":
                    value, i = css_string(css, i)
                    while i < len(css) and css[i] != ")":
                        i += 1
                else:
                    value_parts = []
                    while i < len(css) and css[i] != ")":
                        if css[i] == "\\":
                            char, i = css_escape(css, i)
                            value_parts.append(char)
                        else:
                            value_parts.append(css[i])
                            i += 1
                    value = "".join(value_parts).strip()
                found.append((value, css.count("\n", 0, start)))
                i += i < len(css)
            import_pending = False
            continue
        import_pending = False
        i += 1
    return found


def srcset_urls(value):
    """Read srcset URL tokens without splitting the comma inside data URLs."""
    i = 0
    while i < len(value):
        while i < len(value) and (value[i].isspace() or value[i] == ","):
            i += 1
        start = i
        while i < len(value) and not value[i].isspace():
            i += 1
        url = value[start:i]
        if not url:
            break
        if url.endswith(","):
            yield url.rstrip(",")
            continue
        yield url
        # Descriptor lists can contain parentheses. Commas inside them are not
        # candidate separators; validity of descriptors is a browser concern.
        depth = 0
        while i < len(value):
            char = value[i]
            i += 1
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(0, depth - 1)
            elif char == "," and depth == 0:
                break


class ExplorerParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.links = []
        self.assets = []
        self.bases = []
        self.json_blocks = []
        self.inline_scripts = 0
        self._raw = None
        self._raw_parts = []

    def asset(self, kind, value, line):
        if value is not None:
            self.assets.append({"kind": kind, "url": value, "line": line})

    def css(self, value, line):
        for url, offset in css_urls(value):
            self.asset("css", url, line + offset)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        line = self.getpos()[0]
        self.elements.append({"tag": tag, "attrs": attrs, "line": line})
        if "style" in attrs and attrs["style"] is not None:
            self.css(attrs["style"], line)
        if tag in {"a", "area"} and "href" in attrs:
            self.links.append({"href": attrs["href"] or "", "origin": "static", "line": line})
        if tag == "base" and "href" in attrs:
            self.bases.append({"href": attrs["href"] or "", "line": line})
        if tag == "script":
            self.asset("script", attrs.get("src"), line)
            is_data = attrs.get("id") == "architecture-data" and (attrs.get("type") or "").strip().lower() == "application/json"
            if not attrs.get("src") and not is_data and (attrs.get("type") or "").strip().lower() not in {"application/json", "application/ld+json"}:
                self.inline_scripts += 1
            self._raw = ("json" if is_data else "script", line)
            self._raw_parts = []
        elif tag == "style":
            self._raw = ("style", line)
            self._raw_parts = []
        elif tag == "link":
            rel = set((attrs.get("rel") or "").lower().split())
            if rel.intersection({"stylesheet", "icon", "preload", "modulepreload", "prefetch", "manifest", "apple-touch-icon", "apple-touch-startup-image"}):
                self.asset("link", attrs.get("href"), line)
            for url in srcset_urls(attrs.get("imagesrcset") or ""):
                self.asset("srcset", url, line)
        elif tag in {"img", "audio", "video", "source", "track", "iframe", "embed", "input"}:
            if tag != "input" or (attrs.get("type") or "").lower() == "image":
                self.asset(tag, attrs.get("src"), line)
            if tag == "video":
                self.asset("poster", attrs.get("poster"), line)
            for url in srcset_urls(attrs.get("srcset") or ""):
                self.asset("srcset", url, line)
        elif tag == "object":
            self.asset("object", attrs.get("data"), line)
        elif tag in {"image", "use"}:
            self.asset(tag, attrs.get("href", attrs.get("xlink:href")), line)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        if self._raw:
            self._raw_parts.append(data)

    def handle_endtag(self, tag):
        if not self._raw or tag not in {"script", "style"}:
            return
        kind, line = self._raw
        value = "".join(self._raw_parts)
        if kind == "style":
            self.css(value, line)
        elif kind == "json":
            self.json_blocks.append((value, line))
        self._raw = None
        self._raw_parts = []

    def close(self):
        super().close()
        if self._raw:
            self.handle_endtag("style" if self._raw[0] == "style" else "script")


def parse_html(path):
    parser = ExplorerParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser


class Checker:
    def __init__(self, html, site_root=None, allow_assets=False, rendered_links=None, route_fragments=()):
        self.html = html.resolve()
        self.site_root = (site_root or html.parent).resolve()
        self.allow_assets = allow_assets
        self.rendered_links = rendered_links
        self.route_fragments = set(route_fragments)
        self.findings = []
        self.notes = []
        self.dependencies = []
        self.checked_local_files = set()
        self.checked_fragments = 0
        self.external_links = 0
        self.unvalidated_routes = set()
        self.cache = {}

    def finding(self, code, message, ref="", line=0, origin="static"):
        self.findings.append({"code": code, "message": message, "ref": ref, "line": line, "origin": origin})

    def note(self, code, message, ref="", line=0, origin="static"):
        self.notes.append({"code": code, "message": message, "ref": ref, "line": line, "origin": origin})

    def target(self, value):
        value = clean_url(value)
        try:
            split = urlsplit(value)
        except ValueError as exc:
            return "invalid", str(exc), ""
        scheme = split.scheme.lower()
        if scheme == "javascript":
            return "javascript", "", ""
        if scheme == "data":
            return "data", "", ""
        if scheme == "file" and split.netloc.lower() not in {"", "localhost"}:
            return "remote-file", "", ""
        if split.netloc or scheme not in {"", "file"}:
            return "external", "", ""
        try:
            path = unquote(split.path, errors="strict")
            fragment = unquote(split.fragment, errors="strict")
        except UnicodeDecodeError:
            return "invalid", "URL contains invalid UTF-8 percent encoding", ""
        if "\x00" in path or "\\" in path:
            return "invalid", "Local URL contains a NUL or backslash", ""
        if not path:
            target = self.html
        elif scheme == "file":
            target = Path(path)
        elif path.startswith("/"):
            target = self.site_root / path.lstrip("/")
        else:
            target = self.html.parent / path
        return "local", target.resolve(), fragment

    def check_link(self, link):
        ref, line, origin = link["href"], link["line"], link["origin"]
        kind, target, fragment = self.target(ref)
        if kind == "javascript":
            self.finding("javascript-link", "javascript: links are refused", ref, line, origin)
            return
        if kind == "invalid":
            self.finding("invalid-url", str(target), ref, line, origin)
            return
        if kind == "remote-file":
            self.note("remote-file-unchecked", "Remote file URLs are not accessed", ref, line, origin)
            return
        if kind != "local":
            self.external_links += 1
            return
        if not target.exists():
            self.finding("missing-local-target", "Local target does not exist", ref, line, origin)
            return
        self.checked_local_files.add(str(target))
        if not fragment:
            return
        if target == self.html and fragment in self.route_fragments:
            self.note("declared-application-route", "Flat application route was explicitly declared by the caller; route behavior was not checked", ref, line, origin)
            return
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*(?:/[^/\s]+)+", fragment):
            self.unvalidated_routes.add(fragment)
            self.note("application-hash-unchecked", "Structured application hash requires browser validation", ref, line, origin)
            return
        if target.suffix.lower() not in {".html", ".htm"}:
            self.note("non-html-fragment-unchecked", "Fragment semantics of non-HTML targets are not inferred", ref, line, origin)
            return
        if target not in self.cache:
            try:
                self.cache[target] = parse_html(target)
            except (OSError, UnicodeError, ValueError, RecursionError):
                self.finding("unreadable-fragment-target", "Cannot read HTML target to inspect its fragment", ref, line, origin)
                return
        ids = {element["attrs"].get("id") for element in self.cache[target].elements}
        # Named anchors remain valid fragment targets in HTML.
        ids.update(element["attrs"].get("name") for element in self.cache[target].elements if element["tag"] == "a")
        self.checked_fragments += 1
        if fragment not in ids:
            self.finding("missing-fragment", "HTML fragment has no static id or named anchor", ref, line, origin)

    def check_asset(self, asset):
        ref, line = asset["url"], asset["line"]
        kind, target, fragment = self.target(ref)
        normalized = clean_url(ref)
        inline = kind == "data" or normalized.startswith("#")
        dependency = dict(asset, location="inline" if inline else kind)
        self.dependencies.append(dependency)
        if kind in {"invalid", "javascript"}:
            self.finding("invalid-asset-url", "Asset URL is invalid or uses javascript:", ref, line)
        elif not inline and not self.allow_assets:
            self.finding("non-inline-asset", "Single-file offline mode requires data: or fragment asset URLs", ref, line)
        if kind == "local" and not inline:
            if not target.is_file():
                self.finding("missing-local-asset", "Local asset is missing or is not a file", ref, line)
            else:
                self.checked_local_files.add(str(target))

    def source_links(self, data, line):
        if isinstance(data, dict):
            for key, value in sorted(data.items()):
                if key == "sources":
                    if not isinstance(value, list):
                        self.finding("invalid-sources", "sources must be an array of paths or objects with a path string", "architecture-data", line, "source")
                        continue
                    for entry in value:
                        path = entry if isinstance(entry, str) else entry.get("path") if isinstance(entry, dict) else None
                        if not isinstance(path, str) or not path.strip():
                            self.finding("invalid-source-entry", "Each source must be a nonempty path string or an object with a path string", "architecture-data", line, "source")
                        else:
                            yield {"href": path, "line": line, "origin": "source"}
                else:
                    yield from self.source_links(value, line)
        elif isinstance(data, list):
            for value in data:
                yield from self.source_links(value, line)

    def run(self):
        parser = parse_html(self.html)
        self.cache[self.html] = parser
        ids = {}
        for element in parser.elements:
            identity = element["attrs"].get("id")
            if identity is not None:
                if identity in ids:
                    self.finding("duplicate-id", "Static id appears more than once", identity, element["line"])
                else:
                    ids[identity] = element
        for element in parser.elements:
            attrs, line = element["attrs"], element["line"]
            roles = (attrs.get("role") or "").lower().split()
            if "tab" in roles:
                controls = (attrs.get("aria-controls") or "").split()
                if not controls:
                    self.finding("tab-missing-controls", "Tab must identify its panel using aria-controls", attrs.get("id") or "", line)
                for control in controls:
                    panel = ids.get(control)
                    if panel is None or "tabpanel" not in (panel["attrs"].get("role") or "").lower().split():
                        self.finding("invalid-tab-panel", "aria-controls must resolve to a static tabpanel", control, line)
            if "tabpanel" in roles:
                labels = (attrs.get("aria-labelledby") or "").split()
                if not labels:
                    self.finding("panel-missing-label", "Tabpanel must identify its label using aria-labelledby", attrs.get("id") or "", line)
                for label in labels:
                    if label not in ids:
                        self.finding("missing-panel-label", "Tabpanel label does not exist", label, line)
        for base in parser.bases:
            self.finding("unsupported-base", "base href changes URL resolution and is not supported; local link results assume the HTML directory", base["href"], base["line"])
        links = list(parser.links)
        for block, line in parser.json_blocks:
            try:
                data = strict_json(block)
                links.extend(self.source_links(data, line))
            except (ValueError, RecursionError):
                self.finding("invalid-architecture-json", "architecture-data must contain valid JSON within parser depth limits", "architecture-data", line, "source")
        if self.rendered_links is not None:
            links.extend({"href": href, "origin": "rendered", "line": 0} for href in self.rendered_links)
        for link in links:
            self.check_link(link)
        for asset in parser.assets:
            self.check_asset(asset)
        if self.rendered_links is None:
            self.note("javascript-not-executed", "JavaScript-generated links and interaction behavior were not checked; supply --rendered-links for exported href checks")
        else:
            self.note("browser-export-scope", "Only supplied rendered hrefs were checked; JavaScript behavior, dynamic IDs, routes and export coverage remain browser-verification responsibilities", origin="rendered")
        if self.allow_assets and any(item["location"] == "local" for item in self.dependencies):
            self.note("asset-contents-unchecked", "Referenced asset files are checked for existence only; their contents and transitive dependencies are not inspected")
        sort_key = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=True)
        counts = Counter(link["origin"] for link in links)
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "findings" if self.findings else "ok",
            "html": str(self.html),
            "site_root": str(self.site_root),
            "mode": "allow-assets" if self.allow_assets else "single-file-offline",
            "declared_route_fragments": sorted(self.route_fragments),
            "checks": {
                "static_elements": len(parser.elements), "static_ids": len(ids),
                "static_links": counts["static"], "structured_source_links": counts["source"],
                "rendered_links": counts["rendered"], "rendered_links_supplied": self.rendered_links is not None,
                "local_targets_checked": len(self.checked_local_files), "html_fragments_checked": self.checked_fragments,
                "external_links_not_fetched": self.external_links, "application_hashes_unvalidated": len(self.unvalidated_routes),
                "asset_references": len(self.dependencies), "inline_scripts_not_executed": parser.inline_scripts,
            },
            "dependencies": sorted(self.dependencies, key=sort_key),
            "findings": sorted(self.findings, key=sort_key),
            "notes": sorted(self.notes, key=sort_key),
        }


def main(argv=None):
    parser = JSONArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path, help="HTML explorer to inspect without executing it")
    parser.add_argument("--rendered-links", type=Path, help="JSON array of browser-exported href strings (prefer raw getAttribute('href'))")
    parser.add_argument("--site-root", type=Path, help="Filesystem root for root-relative URLs; defaults to HTML parent")
    parser.add_argument("--allow-assets", action="store_true", help="Permit separate assets; check local existence without reading asset contents")
    parser.add_argument("--route-fragment", action="append", default=[], metavar="NAME", help="Declare one browser-verified flat application hash (without #); repeat for multiple routes")
    try:
        args = parser.parse_args(argv)
        if args.site_root is not None and not args.site_root.is_dir():
            raise InputError("--site-root must be an existing directory")
        if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", route) for route in args.route_fragment):
            raise InputError("--route-fragment must be a flat route name without # or /")
        rendered_links = None
        if args.rendered_links is not None:
            try:
                rendered_links = strict_json(args.rendered_links.read_text(encoding="utf-8"))
            except (ValueError, RecursionError) as exc:
                raise InputError("--rendered-links must contain valid JSON") from exc
            if not isinstance(rendered_links, list) or not all(isinstance(value, str) for value in rendered_links):
                raise InputError("--rendered-links must be a JSON array of href strings")
        result = Checker(args.html, args.site_root, args.allow_assets, rendered_links, args.route_fragment).run()
        code = 1 if result["findings"] else 0
    except (InputError, OSError, UnicodeError, ValueError, RecursionError) as exc:
        result = {"schema_version": SCHEMA_VERSION, "status": "error", "error": str(exc)}
        code = 2
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
