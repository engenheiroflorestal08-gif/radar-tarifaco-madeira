#!/usr/bin/env python3
"""Atualiza o arquivo data/noticias.json a partir de fontes públicas.

O script foi desenhado para rodar diariamente no GitHub Actions, sem chaves de API.
Ele usa RSS do Google News como mecanismo de descoberta, RSS oficial do MDIC e
uma varredura leve das páginas da ABIMCI, USTR e MDIC.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import sys
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote_plus, urljoin, urlparse

import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "monitoramento.json"
DATA_PATH = ROOT / "data" / "noticias.json"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("radar-tarifaco")

USER_AGENT = (
    "Mozilla/5.0 (compatible; RadarTarifacoMadeira/1.0; "
    "+https://github.com/)"
)
SAO_PAULO = timezone(timedelta(hours=-3))


@dataclass
class Article:
    id: str
    titulo: str
    resumo: str
    url: str
    fonte: str
    tipo_fonte: str
    data_publicacao: str
    categoria: str
    prioridade: str
    foco_madeira: bool
    tags: list[str]


def now_sp() -> datetime:
    return datetime.now(tz=SAO_PAULO)


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value


def clean_text(value: str, limit: int = 420) -> str:
    soup = BeautifulSoup(html.unescape(value or ""), "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def make_id(title: str, url: str) -> str:
    key = f"{normalize(title)}|{urlparse(url).netloc}|{urlparse(url).path}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


def build_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7"})
    return session


def parse_date(value: Any, fallback: datetime | None = None) -> datetime:
    fallback = fallback or now_sp()
    if not value:
        return fallback
    if isinstance(value, datetime):
        date = value
    else:
        text = str(value).strip()
        if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", text):
            year, month, day = map(int, text.split("-"))
            return datetime(year, month, day, 12, tzinfo=SAO_PAULO)
        try:
            date = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                date = parsedate_to_datetime(text)
            except (TypeError, ValueError, OverflowError):
                return fallback
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(SAO_PAULO)


def contains_any(text: str, terms: Iterable[str]) -> bool:
    normalized = normalize(text)
    return any(normalize(term) in normalized for term in terms)


def count_terms(text: str, terms: Iterable[str]) -> int:
    normalized = normalize(text)
    return sum(1 for term in terms if normalize(term) in normalized)


def source_type(source: str, url: str, configured: str | None, config: dict[str, Any]) -> str:
    if configured:
        return configured
    domain = urlparse(url).netloc.lower()
    if any(domain.endswith(item) for item in config["fontes_oficiais"]):
        return "Oficial"
    if any(term in normalize(source) for term in ("abimci", "iba", "associacao", "sindicato")):
        return "Setorial"
    return "Imprensa"


def classify(title: str, summary: str, source: str, url: str, configured_type: str | None,
             config: dict[str, Any]) -> tuple[str, str, bool, list[str], str]:
    full = f"{title} {summary} {source} {url}"
    wood_hits = count_terms(full, config["termos_madeira"])
    tariff_hits = count_terms(full, config["termos_tarifarios"])
    trade_hits = count_terms(full, config["termos_comercio"])
    type_name = source_type(source, url, configured_type, config)

    if wood_hits:
        category = "Indústria da madeira"
    elif tariff_hits:
        category = "Política tarifária"
    elif trade_hits:
        category = "Comércio exterior"
    else:
        category = "Economia e indústria"

    score = wood_hits * 3 + tariff_hits * 3 + trade_hits
    if type_name == "Oficial":
        score += 2
    if contains_any(full, ["entra em vigor", "vigência", "final action", "ação final", "ordem executiva"]):
        score += 4
    if contains_any(full, ["brasil", "brazil"]) and contains_any(full, ["estados unidos", "eua", "united states", "ustr"]):
        score += 3

    # Crítico exige forte combinação temática para reduzir alarmes falsos.
    if score >= 17 and tariff_hits and (wood_hits or type_name == "Oficial"):
        priority = "critica"
    elif score >= 11:
        priority = "alta"
    elif score >= 6:
        priority = "media"
    else:
        priority = "baixa"

    tag_candidates = [
        "Seção 301", "Seção 232", "tarifa", "Brasil", "Estados Unidos", "ABIMCI",
        "madeira", "madeira processada", "molduras", "compensado", "madeira serrada",
        "portas", "pisos", "exportações", "Comex Stat", "USTR", "MDIC", "competitividade"
    ]
    tags = [tag for tag in tag_candidates if normalize(tag) in normalize(full)]
    if not tags:
        tags = [category]

    return category, priority, bool(wood_hits), tags[:6], type_name


def is_relevant(title: str, summary: str, config: dict[str, Any]) -> bool:
    full = f"{title} {summary}"
    thematic = (
        contains_any(full, config["termos_tarifarios"])
        or contains_any(full, config["termos_madeira"])
    )
    context = contains_any(full, config["termos_comercio"])
    return thematic and context


def split_google_source(title: str, entry: Any) -> tuple[str, str]:
    source = "Google News"
    if getattr(entry, "source", None):
        source = getattr(entry.source, "title", None) or source
    clean_title = title
    suffix = f" - {source}"
    if source != "Google News" and title.endswith(suffix):
        clean_title = title[: -len(suffix)].strip()
    elif " - " in title:
        possible_title, possible_source = title.rsplit(" - ", 1)
        if 2 <= len(possible_source) <= 80:
            clean_title, source = possible_title.strip(), possible_source.strip()
    return clean_title, source


def article_from_values(title: str, summary: str, url: str, source: str, published: Any,
                        configured_type: str | None, config: dict[str, Any]) -> Article | None:
    title = clean_text(title, 240)
    summary = clean_text(summary)
    url = (url or "").strip()
    if len(title) < 12 or not url or not url.startswith(("http://", "https://")):
        return None
    if not is_relevant(title, summary, config):
        return None

    category, priority, wood, tags, type_name = classify(
        title, summary, source, url, configured_type, config
    )
    date = parse_date(published)
    return Article(
        id=make_id(title, url),
        titulo=title,
        resumo=summary or "Publicação relevante identificada pelo monitoramento. Consulte a fonte para os detalhes.",
        url=url,
        fonte=source or urlparse(url).netloc,
        tipo_fonte=type_name,
        data_publicacao=date.isoformat(),
        categoria=category,
        prioridade=priority,
        foco_madeira=wood,
        tags=tags,
    )


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child_text(element: ET.Element, names: tuple[str, ...]) -> str:
    for child in element.iter():
        if child is element:
            continue
        if local_name(child.tag) in names and child.text:
            return child.text.strip()
    return ""


def parse_feed_entries(content: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(content)
    entries: list[dict[str, str]] = []
    candidates = [el for el in root.iter() if local_name(el.tag) in ("item", "entry")]
    for element in candidates[:100]:
        title = child_text(element, ("title",))
        summary = child_text(element, ("description", "summary", "content"))
        published = child_text(element, ("pubdate", "published", "updated", "date"))
        source = child_text(element, ("source",))
        link = ""
        for child in element.iter():
            if local_name(child.tag) != "link":
                continue
            href = child.attrib.get("href", "").strip()
            rel = child.attrib.get("rel", "alternate")
            if href and rel in ("alternate", ""):
                link = href
                break
            if child.text and child.text.strip():
                link = child.text.strip()
                break
        entries.append({
            "title": title,
            "summary": summary,
            "published": published,
            "source": source,
            "link": link,
        })
    return entries


def fetch_rss(session: requests.Session, name: str, url: str, configured_type: str | None,
              config: dict[str, Any], google_news: bool = False) -> list[Article]:
    logger.info("Consultando RSS: %s", name)
    response = session.get(url, timeout=35)
    response.raise_for_status()
    articles: list[Article] = []

    for entry in parse_feed_entries(response.content):
        title = entry["title"]
        source = entry["source"] or name
        if google_news:
            class Source:
                pass
            fake_entry = Source()
            fake_entry.source = Source()
            fake_entry.source.title = source if source != name else None
            title, source = split_google_source(title, fake_entry)
        article = article_from_values(
            title=title,
            summary=entry["summary"],
            url=entry["link"],
            source=source,
            published=entry["published"] or now_sp().isoformat(),
            configured_type=configured_type,
            config=config,
        )
        if article:
            articles.append(article)
    return articles


def date_near_link(link: Any) -> datetime:
    container = link.find_parent(["article", "li", "div", "section"]) or link.parent
    if container:
        time_tag = container.find("time")
        if time_tag and time_tag.get("datetime"):
            return parse_date(time_tag.get("datetime"))
    context = clean_text(container.get_text(" ", strip=True) if container else "", 500)
    match_br = re.search(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b", context)
    if match_br:
        day, month, year = map(int, match_br.groups())
        return datetime(year, month, day, 12, tzinfo=SAO_PAULO)
    match_iso = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", context)
    if match_iso:
        year, month, day = map(int, match_iso.groups())
        return datetime(year, month, day, 12, tzinfo=SAO_PAULO)

    months_en = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    }
    match_en = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December) "
        r"(\d{1,2}), (20\d{2})\b",
        context,
        flags=re.IGNORECASE,
    )
    if match_en:
        month_name, day, year = match_en.groups()
        return datetime(int(year), months_en[month_name.lower()], int(day), 12, tzinfo=SAO_PAULO)

    months_pt = {
        "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
        "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    }
    normalized_context = normalize(context)
    match_pt = re.search(
        r"\b(\d{1,2}) de (janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro) de (20\d{2})\b",
        normalized_context,
    )
    if match_pt:
        day, month_name, year = match_pt.groups()
        return datetime(int(year), months_pt[month_name], int(day), 12, tzinfo=SAO_PAULO)
    return now_sp()


def scrape_page(session: requests.Session, name: str, url: str, configured_type: str,
                config: dict[str, Any]) -> list[Article]:
    logger.info("Consultando página: %s", name)
    response = session.get(url, timeout=35)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    articles: list[Article] = []
    seen_links: set[str] = set()

    for link in soup.select("a[href]"):
        title = clean_text(link.get_text(" ", strip=True), 240)
        target = urljoin(url, link.get("href", ""))
        if target in seen_links or len(title) < 18:
            continue
        seen_links.add(target)
        if urlparse(target).netloc != urlparse(url).netloc:
            continue

        context = clean_text(link.parent.get_text(" ", strip=True) if link.parent else "", 420)
        article = article_from_values(
            title=title,
            summary=context if context != title else "",
            url=target,
            source=name,
            published=date_near_link(link),
            configured_type=configured_type,
            config=config,
        )
        if article:
            articles.append(article)
    return articles[:50]


def existing_articles() -> list[dict[str, Any]]:
    payload = load_json(DATA_PATH, {"noticias": []})
    return payload.get("noticias", [])


def deduplicate(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    title_keys: set[str] = set()
    priority_order = {"critica": 4, "alta": 3, "media": 2, "baixa": 1}

    sorted_items = sorted(
        items,
        key=lambda item: (
            parse_date(item.get("data_publicacao")).timestamp(),
            priority_order.get(item.get("prioridade", "baixa"), 0),
        ),
        reverse=True,
    )

    for item in sorted_items:
        title_key = re.sub(r"\W+", " ", normalize(item.get("titulo", ""))).strip()[:160]
        item_id = item.get("id") or make_id(item.get("titulo", ""), item.get("url", ""))
        if item_id in by_id or title_key in title_keys:
            continue
        item["id"] = item_id
        by_id[item_id] = item
        title_keys.add(title_key)
    return list(by_id.values())


def main() -> int:
    config = load_json(CONFIG_PATH, {})
    if not config:
        logger.error("Configuração não encontrada: %s", CONFIG_PATH)
        return 1

    session = build_session()
    collected: list[Article] = []
    consulted = 0
    failures: list[str] = []

    for query in config["consultas_google_news"]:
        url = (
            "https://news.google.com/rss/search?q="
            f"{quote_plus(query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        )
        consulted += 1
        try:
            collected.extend(fetch_rss(session, f"Google News: {query}", url, None, config, True))
        except (requests.RequestException, ET.ParseError) as exc:
            failures.append(f"Google News ({query}): {exc}")
            logger.warning("Falha em Google News (%s): %s", query, exc)

    for feed in config["feeds_rss"]:
        consulted += 1
        try:
            collected.extend(fetch_rss(
                session, feed["nome"], feed["url"], feed.get("tipo"), config
            ))
        except (requests.RequestException, ET.ParseError) as exc:
            failures.append(f"{feed['nome']}: {exc}")
            logger.warning("Falha no feed %s: %s", feed["nome"], exc)

    for page in config["paginas_monitoradas"]:
        consulted += 1
        try:
            collected.extend(scrape_page(
                session, page["nome"], page["url"], page.get("tipo", "Imprensa"), config
            ))
        except requests.RequestException as exc:
            failures.append(f"{page['nome']}: {exc}")
            logger.warning("Falha na página %s: %s", page["nome"], exc)

    fresh = [asdict(article) for article in collected]
    old = existing_articles()
    if fresh:
        old = [item for item in old if not str(item.get("id", "")).startswith("demo-")]

    merged = deduplicate([*fresh, *old])
    cutoff = now_sp() - timedelta(days=int(config.get("dias_de_retencao", 180)))
    merged = [item for item in merged if parse_date(item.get("data_publicacao")) >= cutoff]
    merged = merged[: int(config.get("maximo_de_itens", 300))]

    payload = {
        "metadata": {
            "atualizado_em": now_sp().isoformat(),
            "descricao": (
                "Monitoramento automático de notícias públicas sobre tarifas, comércio exterior "
                "e indústria brasileira da madeira."
            ),
            "versao": "1.0.0",
            "total_fontes_consultadas": consulted,
            "novos_itens_encontrados": len(fresh),
            "falhas_de_coleta": failures,
        },
        "noticias": merged,
    }

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info("Arquivo atualizado: %s (%d itens, %d novos)", DATA_PATH, len(merged), len(fresh))
    return 0


if __name__ == "__main__":
    sys.exit(main())
