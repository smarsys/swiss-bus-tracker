import logging
import os
from datetime import datetime, timezone

import httpx
from lxml import etree

from app.models import Departure, DepartureStatus, StopMatch

logger = logging.getLogger(__name__)

NS_OJP = "http://www.vdv.de/ojp"
NS_SIRI = "http://www.siri.org.uk/siri"
NSMAP = {"ojp": NS_OJP, "siri": NS_SIRI}


def _get_config() -> tuple[str, str, str]:
    endpoint = os.getenv("OJP_ENDPOINT", "https://api.opentransportdata.swiss/ojp20")
    api_key = os.getenv("OJP_API_KEY", "")
    user_agent = os.getenv("USER_AGENT", "swiss-bus-tracker/0.1")
    return endpoint, api_key, user_agent


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_location_request(name: str, limit: int = 10) -> str:
    now = _utc_now_iso()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OJP xmlns="http://www.vdv.de/ojp"
     xmlns:siri="http://www.siri.org.uk/siri"
     version="2.0">
    <OJPRequest>
        <siri:ServiceRequest>
            <siri:RequestTimestamp>{now}</siri:RequestTimestamp>
            <siri:RequestorRef>swiss-bus-tracker</siri:RequestorRef>
            <OJPLocationInformationRequest>
                <siri:RequestTimestamp>{now}</siri:RequestTimestamp>
                <siri:MessageIdentifier>LIR-1</siri:MessageIdentifier>
                <InitialInput>
                    <Name>{name}</Name>
                </InitialInput>
                <Restrictions>
                    <Type>stop</Type>
                    <NumberOfResults>{limit}</NumberOfResults>
                </Restrictions>
            </OJPLocationInformationRequest>
        </siri:ServiceRequest>
    </OJPRequest>
</OJP>"""


def build_stop_event_request(stop_ref: str, dep_time: str, num_results: int = 10) -> str:
    now = _utc_now_iso()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OJP xmlns="http://www.vdv.de/ojp"
     xmlns:siri="http://www.siri.org.uk/siri"
     version="2.0">
    <OJPRequest>
        <siri:ServiceRequest>
            <siri:RequestTimestamp>{now}</siri:RequestTimestamp>
            <siri:RequestorRef>swiss-bus-tracker</siri:RequestorRef>
            <OJPStopEventRequest>
                <siri:RequestTimestamp>{now}</siri:RequestTimestamp>
                <siri:MessageIdentifier>SER-1</siri:MessageIdentifier>
                <Location>
                    <PlaceRef>
                        <StopPlaceRef>{stop_ref}</StopPlaceRef>
                        <Name><Text>stop</Text></Name>
                    </PlaceRef>
                    <DepArrTime>{dep_time}</DepArrTime>
                </Location>
                <Params>
                    <NumberOfResults>{num_results}</NumberOfResults>
                    <StopEventType>departure</StopEventType>
                    <IncludePreviousCalls>false</IncludePreviousCalls>
                    <IncludeOnwardCalls>false</IncludeOnwardCalls>
                    <IncludeOperatingDays>false</IncludeOperatingDays>
                    <UseRealtimeData>explanatory</UseRealtimeData>
                </Params>
            </OJPStopEventRequest>
        </siri:ServiceRequest>
    </OJPRequest>
</OJP>"""


def parse_location_response(xml_bytes: bytes) -> list[StopMatch]:
    root = etree.fromstring(xml_bytes)
    results = []
    for pr in root.findall(".//ojp:PlaceResult", NSMAP):
        stop_place = pr.find(".//ojp:StopPlace", NSMAP)
        if stop_place is None:
            continue
        ref_el = stop_place.find("ojp:StopPlaceRef", NSMAP)
        name_el = stop_place.find("ojp:StopPlaceName/ojp:Text", NSMAP)
        geo = pr.find(".//ojp:GeoPosition", NSMAP)
        lat = lon = 0.0
        if geo is not None:
            lat_el = geo.find("siri:Latitude", NSMAP)
            lon_el = geo.find("siri:Longitude", NSMAP)
            if lat_el is not None and lat_el.text:
                lat = float(lat_el.text)
            if lon_el is not None and lon_el.text:
                lon = float(lon_el.text)
        display_name_el = pr.find("ojp:Place/ojp:Name/ojp:Text", NSMAP)
        display_name = display_name_el.text if display_name_el is not None and display_name_el.text else ""
        locality = ""
        if display_name and "(" in display_name and ")" in display_name:
            locality = display_name.split("(")[-1].rstrip(")")

        results.append(StopMatch(
            stop_ref=ref_el.text if ref_el is not None and ref_el.text else "",
            name=name_el.text if name_el is not None and name_el.text else "",
            locality=locality,
            lat=lat,
            lon=lon,
        ))
    return results


def parse_stop_event_response(xml_bytes: bytes, now: datetime | None = None) -> list[Departure]:
    if now is None:
        now = datetime.now(timezone.utc)
    root = etree.fromstring(xml_bytes)
    results = []
    for ser in root.findall(".//ojp:StopEventResult", NSMAP):
        se = ser.find("ojp:StopEvent", NSMAP)
        if se is None:
            continue
        call = se.find("ojp:ThisCall/ojp:CallAtStop", NSMAP)
        service = se.find("ojp:Service", NSMAP)
        if call is None or service is None:
            continue

        timetabled_el = call.find("ojp:ServiceDeparture/ojp:TimetabledTime", NSMAP)
        estimated_el = call.find("ojp:ServiceDeparture/ojp:EstimatedTime", NSMAP)
        stop_name_el = call.find("ojp:StopPointName/ojp:Text", NSMAP)
        line_el = service.find("ojp:PublishedServiceName/ojp:Text", NSMAP)
        dest_el = service.find("ojp:DestinationText/ojp:Text", NSMAP)
        cancelled_el = service.find("ojp:Cancelled", NSMAP)
        mode_el = service.find("ojp:Mode/ojp:PtMode", NSMAP)

        if timetabled_el is None or timetabled_el.text is None:
            continue

        scheduled_time = datetime.fromisoformat(timetabled_el.text)
        estimated_time = None
        if estimated_el is not None and estimated_el.text:
            estimated_time = datetime.fromisoformat(estimated_el.text)

        cancelled = cancelled_el is not None and cancelled_el.text and cancelled_el.text.lower() == "true"

        dep = Departure(
            line=line_el.text if line_el is not None and line_el.text else "",
            destination=dest_el.text if dest_el is not None and dest_el.text else "",
            scheduled_time=scheduled_time,
            estimated_time=estimated_time,
            stop_name=stop_name_el.text if stop_name_el is not None and stop_name_el.text else "",
            mode=mode_el.text if mode_el is not None and mode_el.text else "",
            status=DepartureStatus.cancelled if cancelled else DepartureStatus.unknown,
        )
        dep.compute_status_and_delay(now)
        results.append(dep)

    results.sort(key=lambda d: d.scheduled_time)
    return results


async def search_stops(name: str, limit: int = 10) -> list[StopMatch]:
    endpoint, api_key, user_agent = _get_config()
    xml_body = build_location_request(name, limit)
    logger.debug("OJP LocationInformationRequest XML:\n%s", xml_body)
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        resp = await client.post(
            endpoint,
            content=xml_body.encode("utf-8"),
            headers={
                "Content-Type": "application/xml",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": user_agent,
            },
        )
    if resp.status_code != 200:
        raise OJPError(f"OJP returned {resp.status_code}: {resp.text[:500]}")
    return parse_location_response(resp.content)


async def get_stop_events(
    stop_ref: str,
    window_min: int = 60,
    num_results: int = 10,
) -> list[Departure]:
    endpoint, api_key, user_agent = _get_config()
    now = datetime.now(timezone.utc)
    dep_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    xml_body = build_stop_event_request(stop_ref, dep_time, num_results)
    logger.debug("OJP StopEventRequest XML:\n%s", xml_body)
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        resp = await client.post(
            endpoint,
            content=xml_body.encode("utf-8"),
            headers={
                "Content-Type": "application/xml",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": user_agent,
            },
        )
    if resp.status_code != 200:
        raise OJPError(f"OJP returned {resp.status_code}: {resp.text[:500]}")
    return parse_stop_event_response(resp.content, now)


class OJPError(Exception):
    pass
