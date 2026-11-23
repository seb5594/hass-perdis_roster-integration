"""Transit operators known to run a public MOBILE-PERDIS portal.

Every entry was checked by opening its login page: the address answers with the PERDIS WebComm
login form (only the WSW portal once answered "temporarily unavailable").
Nothing here is endorsed by the operators or by INIT; it only saves people from looking up the
address of their own portal. An operator that is missing can always be
added by hand in the setup dialog ("Enter the address myself").

To add an operator, append an `Operator` and keep the list sorted by name.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from .const import PortalType


@dataclass(frozen=True, slots=True)
class Operator:
    """A transit operator and the address of its Perdis portal."""

    key: str
    name: str
    region: str
    country: str
    url: str
    portal_type: PortalType = PortalType.WEBCOMM

    @property
    def label(self) -> str:
        """Text shown in the setup dialog, e.g. "Rheinbahn · Düsseldorf (DE)"."""
        return f"{self.name} · {self.region} ({self.country})"


OPERATORS: tuple[Operator, ...] = (
    Operator("bogestra", "BOGESTRA", "Bochum / Gelsenkirchen", "DE",
             "https://webcomm.bogestra.de/WebComm/"),
    Operator("dvg_duisburg", "DVG Duisburger Verkehrsgesellschaft", "Duisburg", "DE",
             "https://perdis.dvv.de/WebComm/"),
    Operator("regiobus_hannover", "RegioBus Hannover", "Region Hannover", "DE",
             "https://perdis.regiobus.de/WebComm/"),
    Operator("rheinbahn", "Rheinbahn", "Düsseldorf", "DE",
             "https://webcom.rheinbahn.de/WebComm/"),
    Operator("rnv", "rnv Rhein-Neckar-Verkehr", "Mannheim / Heidelberg / Ludwigshafen", "DE",
             "https://fahrerauskunft.rnv-online.de/WebComm/"),
    Operator("salzburg_ag", "Salzburg AG Verkehr", "Salzburg", "AT",
             "https://perdis.salzburg-ag.at/WebComm/"),
    Operator("transdev_nl", "Transdev / Connexxion", "Nederland", "NL",
             "https://diensten1.transdev.nl/WebComm/"),
    Operator("uestra", "üstra Hannoversche Verkehrsbetriebe", "Hannover", "DE",
             "https://wbc.uestra.de/WebComm/"),
    Operator("vgf", "VGF Verkehrsgesellschaft Frankfurt", "Frankfurt am Main", "DE",
             "https://perdis-info.vgf-ffm.de/WebComm/"),
    Operator("wsw", "WSW mobil", "Wuppertal", "DE",
             "https://service.wsw-online.de/WebComm/"),
)

OPERATORS_BY_KEY: dict[str, Operator] = {operator.key: operator for operator in OPERATORS}


def find_operator_by_url(url: str) -> Operator | None:
    """The known operator whose portal lives on the host of `url`, if any."""
    host = urlsplit(url).hostname
    return next((op for op in OPERATORS if urlsplit(op.url).hostname == host), None)
