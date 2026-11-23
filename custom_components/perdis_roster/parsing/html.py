"""A small HTML tree built on the standard library, just enough for WebComm pages.

Home Assistant runs on very small machines too, so the integration does without BeautifulSoup
and lxml: Python's own `html.parser` builds a light tree, and the helpers below answer the only
questions the integration asks of a page - which forms, tables and links it has.

Browsers forgive missing end tags (`<td>` without `</td>`), and so does this tree: a new cell
closes the previous one, a new row closes the previous row, and so on.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser
import re

VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr",
})
# A start tag of the key closes an open element of the listed tags, up to the boundary tags.
IMPLICIT_CLOSE: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "tr": (frozenset({"tr", "td", "th"}), frozenset({"table", "thead", "tbody", "tfoot"})),
    "td": (frozenset({"td", "th"}), frozenset({"tr", "table"})),
    "th": (frozenset({"td", "th"}), frozenset({"tr", "table"})),
    "thead": (frozenset({"thead", "tbody", "tr", "td", "th"}), frozenset({"table"})),
    "tbody": (frozenset({"thead", "tbody", "tr", "td", "th"}), frozenset({"table"})),
    "li": (frozenset({"li"}), frozenset({"ul", "ol"})),
    "option": (frozenset({"option"}), frozenset({"select"})),
    "p": (frozenset({"p"}), frozenset({"div", "td", "th", "li", "body"})),
}
WHITESPACE = re.compile(r"\s+")


@dataclass(eq=False)
class Element:
    """One element of the tree with its attributes, children and text."""

    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Element | str] = field(default_factory=list)
    parent: Element | None = None

    def get(self, name: str, default: str = "") -> str:
        return self.attrs.get(name, default)

    def iter(self) -> Iterator[Element]:
        """This element and all elements below it, in document order."""
        yield self
        for child in self.children:
            if isinstance(child, Element):
                yield from child.iter()

    def find_all(self, tags: str | set[str] | None = None,
                 where: Callable[[Element], bool] | None = None) -> list[Element]:
        wanted = {tags} if isinstance(tags, str) else tags
        return [element for element in self.iter()
                if (wanted is None or element.tag in wanted) and (where is None or where(element))]

    def find(self, tags: str | set[str] | None = None,
             where: Callable[[Element], bool] | None = None) -> Element | None:
        return next(iter(self.find_all(tags, where)), None)

    def text(self) -> str:
        """All text below the element, with whitespace collapsed like a browser shows it."""
        parts: list[str] = []
        self._collect_text(parts)
        return WHITESPACE.sub(" ", " ".join(parts)).strip()

    def _collect_text(self, parts: list[str]) -> None:
        if self.tag in {"script", "style"}:
            return
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            else:
                if child.tag == "br":
                    parts.append(" ")
                child._collect_text(parts)

    def ancestor(self, tag: str) -> Element | None:
        node = self.parent
        while node is not None and node.tag != tag:
            node = node.parent
        return node


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Element("#document")
        self._stack: list[Element] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._close_implicitly(tag)
        element = Element(tag, {name: value or "" for name, value in attrs}, parent=self._stack[-1])
        self._stack[-1].children.append(element)
        if tag not in VOID_TAGS:
            self._stack.append(element)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self._stack.pop()

    def handle_endtag(self, tag: str) -> None:
        for depth in range(len(self._stack) - 1, 0, -1):
            if self._stack[depth].tag == tag:
                del self._stack[depth:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)

    def _close_implicitly(self, tag: str) -> None:
        if tag not in IMPLICIT_CLOSE:
            return
        closes, boundary = IMPLICIT_CLOSE[tag]
        for depth in range(len(self._stack) - 1, 0, -1):
            current = self._stack[depth].tag
            if current in boundary:
                return
            if current in closes:
                del self._stack[depth:]
                return


def parse_html(markup: str) -> Element:
    """The document tree of `markup`; never raises on broken HTML."""
    builder = _TreeBuilder()
    builder.feed(markup)
    builder.close()
    return builder.root


# --- Questions the integration asks of a page ------------------------------------------------

@dataclass(slots=True)
class Form:
    """A form as a browser would submit it, plus the login fields when it is a login form."""

    action: str
    fields: dict[str, str]
    username_field: str | None = None
    password_field: str | None = None
    submit: tuple[str, str] | None = None
    postbacks: list[PostBack] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class PostBack:
    """A control that submits the ASP.NET form: a button or a `__doPostBack` link."""

    text: str
    target: str
    argument: str = ""
    is_button: bool = False
    value: str = ""


POSTBACK_CALL = re.compile(r"__doPostBack\(\s*['\"]([^'\"]*)['\"]\s*,\s*['\"]([^'\"]*)['\"]")


def _field_value(element: Element) -> str | None:
    """The value a browser would send for an input or select; None when it sends nothing."""
    if element.tag == "select":
        options = element.find_all("option")
        chosen = next((o for o in options if "selected" in o.attrs), options[0] if options else None)
        return (chosen.get("value") or chosen.text()) if chosen else None
    kind = element.get("type", "text").lower()
    if kind in {"checkbox", "radio"}:
        return element.get("value", "on") if "checked" in element.attrs else None
    if kind in {"submit", "button", "image", "reset", "file"}:
        return None
    return element.get("value")


def _label(element: Element) -> str:
    """What a user sees on a control: its text, tooltip, value or image description."""
    return (element.text() or element.get("title") or element.get("value") or element.get("alt")).strip()


def _postbacks(form: Element) -> list[PostBack]:
    """Submit buttons and `__doPostBack` links of a form (paging, period selection, ...)."""
    found: list[PostBack] = []
    for element in form.iter():
        if element.tag == "input" and element.get("type", "").lower() in {"submit", "image"} and element.get("name"):
            found.append(PostBack(_label(element), element.get("name"), is_button=True, value=element.get("value")))
            continue
        call = POSTBACK_CALL.search(element.get("href")) or POSTBACK_CALL.search(element.get("onclick"))
        if call:
            found.append(PostBack(_label(element), call.group(1), call.group(2)))
    return found


def parse_forms(document: Element) -> list[Form]:
    """Every form of the page with the values a browser would submit."""
    forms: list[Form] = []
    for element in document.find_all("form"):
        form = Form(action=element.get("action"), fields={})
        for control in element.find_all({"input", "select", "textarea"}):
            name = control.get("name")
            if not name:
                continue
            kind = control.get("type", "text").lower()
            if control.tag == "input" and kind == "password":
                form.password_field = form.password_field or name
            elif control.tag == "input" and kind in {"text", "email", "tel", "number", ""} and not form.username_field:
                form.username_field = name
            elif control.tag == "input" and kind == "submit" and form.submit is None:
                form.submit = (name, control.get("value"))
            value = control.text() if control.tag == "textarea" else _field_value(control)
            if value is not None:
                form.fields[name] = value
        form.postbacks = _postbacks(element)
        forms.append(form)
    return forms


def login_form(document: Element) -> Form | None:
    """The form that asks for a password, if the page has one."""
    return next((form for form in parse_forms(document) if form.password_field), None)


def links(document: Element) -> list[tuple[str, str]]:
    """(text, href) of every link with a real target, in document order."""
    found = []
    for anchor in document.find_all("a"):
        href = anchor.get("href").strip()
        if href and not href.startswith(("#", "javascript:", "mailto:")):
            found.append((anchor.text() or anchor.get("title"), href))
    return found


def table_rows(table: Element) -> list[tuple[bool, list[str]]]:
    """Rows of a table that belong to it (not to nested tables) as (is_header, cell texts)."""
    rows = []
    for row in table.find_all("tr", lambda tr: tr.ancestor("table") is table):
        cells = [cell for cell in row.children if isinstance(cell, Element) and cell.tag in {"td", "th"}]
        if not cells:
            continue
        expanded: list[str] = []
        for cell in cells:
            span = int(cell.get("colspan", "1")) if cell.get("colspan", "1").isdigit() else 1
            expanded.extend([cell.text()] * max(span, 1))
        is_header = all(cell.tag == "th" for cell in cells) or row.ancestor("thead") is not None
        rows.append((is_header, expanded))
    return rows


def innermost_tables(document: Element) -> list[Element]:
    """Tables that contain no other table: layout tables only wrap the real data."""
    return [table for table in document.find_all("table")
            if not any(inner is not table for inner in table.find_all("table"))]
