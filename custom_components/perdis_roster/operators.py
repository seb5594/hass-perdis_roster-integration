"""Transit operators known to run a public MOBILE-PERDIS portal.

Every entry was checked by opening its login page (WVV, Ruhrbahn and NVG were handed over
by users and could not be opened from the checking machine): the address answers with the PERDIS WebComm
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
    """A transit operator and the address of its PERDIS portal."""

    key: str
    name: str
    region: str
    country: str
    url: str
    portal_type: PortalType = PortalType.WEBCOMM
    short_name: str = ""  # for names whose first word says too little, e.g. "Stadtwerke Bielefeld"

    @property
    def label(self) -> str:
        """Text shown in the setup dialog, e.g. "Rheinbahn · Düsseldorf (DE)"."""
        return f"{self.name} · {self.region} ({self.country})"

    @property
    def short(self) -> str:
        """The operator's short name, e.g. "VGF", "DVG" or "Rheinbahn": the first word of the name,
        unless a short name is set."""
        return self.short_name or self.name.split()[0]


OPERATORS: tuple[Operator, ...] = (
    Operator("bogestra", "BOGESTRA", "Bochum / Gelsenkirchen", "DE",
             "https://webcomm.bogestra.de/WebComm/"),
    Operator("dvg_duisburg", "DVG Duisburger Verkehrsgesellschaft", "Duisburg", "DE",
             "https://perdis.dvv.de/WebComm/"),
    Operator("icb_frankfurt", "ICB In der City Bus", "Frankfurt am Main", "DE",
             "https://perdis-info.icb-ffm.de/WebComm/"),
    Operator("nvg", "NVG", "nvgweb.de", "DE",
             "http://nvgweb.de/WebComm/"),
    Operator("regiobus_hannover", "RegioBus Hannover", "Region Hannover", "DE",
             "https://perdis.regiobus.de/WebComm/"),
    Operator("ret_rotterdam", "RET Rotterdamse Elektrische Tram", "Rotterdam", "NL",
             "https://perdismobcomm.ret.nl/WebComm/"),
    Operator("rheinbahn", "Rheinbahn", "Düsseldorf", "DE",
             "https://webcom.rheinbahn.de/WebComm/"),
    Operator("rnv", "rnv Rhein-Neckar-Verkehr", "Mannheim / Heidelberg / Ludwigshafen", "DE",
             "https://fahrerauskunft.rnv-online.de/WebComm/"),
    Operator("ruhrbahn", "Ruhrbahn", "Essen / Mülheim", "DE",
             "https://perdisweb.ruhrbahn.de/WebComm/"),
    Operator("salzburg_ag", "Salzburg AG Verkehr", "Salzburg", "AT",
             "https://perdis.salzburg-ag.at/WebComm/"),
    Operator("stadtwerke_bielefeld", "Stadtwerke Bielefeld", "Bielefeld", "DE",
             "https://anwendungen.stadtwerke-bielefeld.de/WebComm/", short_name="SW Bielefeld"),
    Operator("stadtwerke_hamm", "Stadtwerke Hamm", "Hamm", "DE",
             "https://perdis.stadtwerke-hamm.de/WebComm/", short_name="SW Hamm"),
    Operator("stadtwerke_muenster", "Stadtwerke Münster", "Münster", "DE",
             "https://verkehr.stadtwerke-muenster.de/WebComm/", short_name="SW Münster"),
    Operator("tower_transit_sg", "Tower Transit Singapore", "Singapore", "SG",
             "https://perdis.towertransit.sg/WebComm/", short_name="Tower Transit"),
    Operator("transdev_nl", "Transdev / Connexxion", "Nederland", "NL",
             "https://diensten1.transdev.nl/WebComm/"),
    Operator("uestra", "ÜSTRA Hannoversche Verkehrsbetriebe", "Hannover", "DE",
             "https://wbc.uestra.de/WebComm/"),
    Operator("vgf", "VGF Verkehrsgesellschaft Frankfurt", "Frankfurt am Main", "DE",
             "https://perdis-info.vgf-ffm.de/WebComm/"),
    Operator("wsw", "WSW mobil", "Wuppertal", "DE",
             "https://service.wsw-online.de/WebComm/"),
    Operator("wvv", "WVV Würzburger Versorgungs- und Verkehrs-GmbH", "Würzburg", "DE",
             "https://perdisapp.wvv.de:1443/WebCommprod/"),
)

OPERATORS_BY_KEY: dict[str, Operator] = {operator.key: operator for operator in OPERATORS}


def find_operator_by_url(url: str) -> Operator | None:
    """The known operator whose portal lives on the host of `url`, if any."""
    host = urlsplit(url).hostname
    return next((op for op in OPERATORS if urlsplit(op.url).hostname == host), None)
