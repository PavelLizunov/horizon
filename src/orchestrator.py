"""Main orchestrator coordinating the entire workflow."""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional
from urllib.parse import unquote_plus, urlsplit
import httpx
from rich.console import Console

from .console_icons import get_icons
from .models import Config, ContentItem
from .storage.manager import StorageManager
from .services.email import EmailManager
from .services.webhook import WebhookNotifier
from .services.search import SearchIndexer, build_search_documents
from .scrapers.github import GitHubScraper
from .scrapers.hackernews import HackerNewsScraper
from .scrapers.rss import RSSScraper
from .scrapers.reddit import RedditScraper
from .scrapers.telegram import TelegramScraper
from .scrapers.twitter import TwitterScraper
from .scrapers.twitter_playwright import TwitterPlaywrightScraper
from .scrapers.openbb import OpenBBScraper
from .scrapers.ossinsight import OSSInsightScraper
from .scrapers.gdelt import GDELTScraper
from .scrapers.google_news import GoogleNewsScraper
from .scrapers.video import VideoScraper
from .ai.client import create_ai_client
from .ai.analyzer import ContentAnalyzer
from .ai.summarizer import DailySummarizer
from .ai.enricher import ContentEnricher, EnrichmentBatchResult
from .ai.tokens import get_usage_snapshot
from .processing import ProfileRegistry
from .verification.ledger import ShadowLedger, select_shadow_items
from .verification.claims import ClaimExtractionOutcome, ClaimExtractor
from .verification.evidence import (
    EvidenceVerifier,
    ItemVerificationBudget,
    build_public_verification,
    build_token_usage_report,
    build_verification_report,
    verification_error_result,
)
from .verification.audit import ArtifactAuditOutcome, ArtifactAuditor


_TRACKING_QUERY_PARAMETERS = {
    "_ga",
    "dclid",
    "fbclid",
    "gclid",
    "igshid",
    "li_fat_id",
    "mc_cid",
    "mc_eid",
    "msclkid",
    "ttclid",
    "twclid",
    "vero_id",
}


def _deduplication_url_key(url: str) -> tuple[str, str, str, str, Optional[int], str, str]:
    """Return a conservative URL identity key for cross-source deduplication."""
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if (scheme, port) in {("http", 80), ("https", 443)}:
        port = None

    path = parsed.path.rstrip("/") or "/"
    query_parts = []
    for part in parsed.query.split("&") if parsed.query else []:
        name = unquote_plus(part.partition("=")[0]).lower()
        if name.startswith("utm_") or name in _TRACKING_QUERY_PARAMETERS:
            continue
        query_parts.append(part)

    return (
        scheme,
        parsed.username or "",
        parsed.password or "",
        host,
        port,
        path,
        "&".join(query_parts),
    )


@dataclass
class BalancedDigestResult:
    """Items and selection statistics from balanced digest filtering."""

    items: List[ContentItem]
    enabled: bool = False
    group_counts: Dict[str, int] = field(default_factory=dict)
    group_limits: Dict[str, Optional[int]] = field(default_factory=dict)
    duplicate_categories: List[str] = field(default_factory=list)


@dataclass
class FilteringPipelineResult:
    """Items and statistics from score, topic, and digest filtering."""

    items: List[ContentItem]
    threshold_count: int
    topic_dedup_count: int
    topic_dedup_removed: int
    balanced_digest: BalancedDigestResult
    eligible_count: Optional[int] = None


@dataclass
class SourceFetchOutcome:
    """Result of fetching one configured source."""

    source_name: str
    status: Literal["success", "empty", "failure"]
    items: List[ContentItem] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        result: Dict[str, object] = {
            "source": self.source_name,
            "status": self.status,
            "item_count": len(self.items),
        }
        if self.error is not None:
            result["error"] = self.error
        return result


@dataclass
class FetchReport:
    """Aggregate diagnostics for one fetch across configured sources."""

    outcomes: List[SourceFetchOutcome] = field(default_factory=list)

    @property
    def status(self) -> Literal["not_attempted", "success", "partial_failure", "failure"]:
        if not self.outcomes:
            return "not_attempted"
        if self.failed_count == len(self.outcomes):
            return "failure"
        if self.failed_count:
            return "partial_failure"
        return "success"

    @property
    def failed_count(self) -> int:
        return sum(outcome.status == "failure" for outcome in self.outcomes)

    @property
    def all_failed(self) -> bool:
        return bool(self.outcomes) and self.failed_count == len(self.outcomes)

    def failure_message(self) -> str:
        failures = "; ".join(
            f"{outcome.source_name}: {outcome.error or 'unknown error'}"
            for outcome in self.outcomes
            if outcome.status == "failure"
        )
        return f"All {len(self.outcomes)} attempted sources failed ({failures})"

    def to_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "attempted": len(self.outcomes),
            "successful": len(self.outcomes) - self.failed_count,
            "empty": sum(outcome.status == "empty" for outcome in self.outcomes),
            "failed": self.failed_count,
            "item_count": sum(len(outcome.items) for outcome in self.outcomes),
            "sources": [outcome.to_dict() for outcome in self.outcomes],
        }


class HorizonOrchestrator:
    """Orchestrates the complete workflow for content aggregation and analysis."""

    icons = get_icons()

    def __init__(
        self,
        config: Config,
        storage: StorageManager,
        console: Optional[Console] = None,
        profiles: Optional[ProfileRegistry] = None,
    ):
        """Initialize orchestrator.

        Args:
            config: Application configuration
            storage: Storage manager
            console: Shared Rich Console instance
        """
        self.config = config
        self.storage = storage
        self.console = console or Console(stderr=True)
        self.icons = get_icons(config.display.icon_style)
        self.profiles = profiles or ProfileRegistry.load(
            Path(config.processing.profiles_dir), config.processing.default_profile
        )
        self.profiles.validate_source_references(
            config.sources.model_dump(mode="json")
        )
        for profile_id in config.processing.profile_settings:
            self.profiles.get(profile_id)
        if config.digest.profile_order:
            configured_profiles = set(config.digest.profile_order)
            missing_profiles = self.profiles.ids - configured_profiles
            unknown_profiles = configured_profiles - self.profiles.ids
            if missing_profiles or unknown_profiles:
                details = []
                if missing_profiles:
                    details.append(f"missing: {', '.join(sorted(missing_profiles))}")
                if unknown_profiles:
                    details.append(f"unknown: {', '.join(sorted(unknown_profiles))}")
                raise ValueError(
                    "digest.profile_order must list every loaded profile exactly once "
                    f"({'; '.join(details)})"
                )
        self.email_manager = EmailManager(config.email, console=self.console) if config.email else None
        self.webhook_notifier = (
            WebhookNotifier(
                config.webhook,
                console=self.console,
                icons=self.icons,
                brand=config.digest.brand,
            )
            if config.webhook and config.webhook.enabled
            else None
        )
        self.last_fetch_report: Optional[FetchReport] = None
        # Profiles already warned about for having no threshold (once each).
        self._thresholdless_profiles: set[str] = set()

    async def run(self, force_hours: int = None) -> None:
        """Execute the complete workflow.

        Args:
            force_hours: Optional override for time window in hours
        """
        self.console.print(
            f"[bold cyan]{self.icons['start']} Horizon - Starting aggregation...[/bold cyan]\n"
        )

        # Check email subscriptions if configured
        if (
            self.email_manager
            and self.config.email
            and self.config.email.enabled
            and self.config.email.imap_enabled
        ):
            self.console.print(f"{self.icons['email']} Checking for new email subscriptions...")
            self.email_manager.check_subscriptions(self.storage)

        try:
            # 1. Determine time window
            since = self._determine_time_window(force_hours)
            self.console.print(
                f"{self.icons['date']} Fetching content since: "
                f"{since.strftime('%Y-%m-%d %H:%M:%S')}\n"
            )

            # 2. Fetch content from all sources
            all_items = await self.fetch_all_sources(since)
            self.console.print(
                f"{self.icons['fetched']} Fetched {len(all_items)} items from all sources\n"
            )

            if self.last_fetch_report and self.last_fetch_report.all_failed:
                raise RuntimeError(self.last_fetch_report.failure_message())

            verification_ledger = None
            url_dedup_members = None
            topic_dedup_members = None
            verification_config = getattr(self.config, "verification", None)
            if verification_config is not None and verification_config.enabled:
                known_limits = {
                    item.id: self.config.sources.video.transcript_max_chars
                    for item in all_items
                    if item.source_type.value == "video"
                }
                try:
                    verification_ledger = ShadowLedger.start(
                        all_items,
                        known_content_limits=known_limits,
                    )
                    url_dedup_members = {}
                    topic_dedup_members = {}
                except Exception as verification_error:
                    self.console.print(
                        f"[yellow]{self.icons['warning']} Verification input capture "
                        f"failed; publication is unchanged: {verification_error}[/yellow]\n"
                    )

            if not all_items:
                self.console.print("[yellow]No new content found. Exiting.[/yellow]")
                return

            # 3. Merge cross-source duplicates (same URL from different sources)
            if url_dedup_members is None:
                merged_items = self.merge_cross_source_duplicates(all_items)
            else:
                merged_items = self.merge_cross_source_duplicates(
                    all_items,
                    member_map=url_dedup_members,
                )
            if len(merged_items) < len(all_items):
                self.console.print(
                    f"{self.icons['merge']} Merged "
                    f"{len(all_items) - len(merged_items)} cross-source duplicates "
                    f"→ {len(merged_items)} unique items\n"
                )

            # 4. Analyze with AI
            analyzed_items = await self.analyze_items(merged_items)
            self.console.print(
                f"{self.icons['ai']} Analyzed {len(analyzed_items)} items with AI\n"
            )

            # 5. Filter, deduplicate, and balance the digest
            if topic_dedup_members is None:
                filtering_result = await self.select_digest_items(analyzed_items)
            else:
                filtering_result = await self.select_digest_items(
                    analyzed_items,
                    topic_member_map=topic_dedup_members,
                )
            important_items = filtering_result.items

            if verification_ledger is not None:
                try:
                    verification_ledger.capture_selected(
                        select_shadow_items(
                            important_items,
                            verification_config.max_items_per_run,
                        ),
                        url_dedup_members=url_dedup_members or {},
                        topic_dedup_members=topic_dedup_members or {},
                    )
                except Exception as verification_error:
                    self.console.print(
                        f"[yellow]{self.icons['warning']} Verification selection capture "
                        f"failed; publication is unchanged: {verification_error}[/yellow]\n"
                    )
                    verification_ledger = None

            # Show per-sub-source selection breakdown
            selected_counts: Dict[str, int] = defaultdict(int)
            for item in important_items:
                key = f"{item.source_type.value}/{self._sub_source_label(item)}"
                selected_counts[key] += 1
            for source_key, count in sorted(selected_counts.items()):
                self.console.print(f"      {self.icons['detail']} {source_key}: {count}")
            self.console.print("")

            # 6. Search related stories + enrich with background knowledge (2nd AI pass)
            await self.enrich_items(important_items)

            if verification_ledger is not None:
                try:
                    snapshots = verification_ledger.selected_snapshots
                    claim_client = None
                    claim_elapsed: Dict[str, float] = {}
                    claim_token_usage: Dict[str, tuple[int, int, int]] = {}
                    if not snapshots:
                        claim_outcomes = []
                    else:
                        try:
                            claim_client = create_ai_client(self.config.ai)
                        except Exception:
                            claim_outcomes = [
                                ClaimExtractionOutcome(
                                    selected_input_snapshot_id=snapshot.snapshot_id,
                                    item_id=snapshot.item_id,
                                    status="error",
                                    error_code="model_error",
                                    model=self.config.ai.model,
                                    model_calls=0,
                                )
                                for snapshot in snapshots
                            ]
                        else:
                            extractor = ClaimExtractor(
                                claim_client,
                                max_claims=verification_config.max_core_claims_per_item,
                            )
                            claim_outcomes = []
                            for snapshot in snapshots:
                                usage_before = get_usage_snapshot()
                                started = asyncio.get_running_loop().time()
                                try:
                                    async with asyncio.timeout(
                                        verification_config.timeout_seconds_per_item
                                    ):
                                        outcome = await extractor.extract(snapshot)
                                except TimeoutError:
                                    outcome = ClaimExtractionOutcome(
                                        selected_input_snapshot_id=snapshot.snapshot_id,
                                        item_id=snapshot.item_id,
                                        status="error",
                                        error_code="timeout",
                                        model=self.config.ai.model,
                                        duration_seconds=(
                                            asyncio.get_running_loop().time() - started
                                        ),
                                    )
                                claim_outcomes.append(outcome)
                                usage_after = get_usage_snapshot()
                                claim_token_usage[snapshot.snapshot_id] = (
                                    usage_after.total_input_tokens
                                    - usage_before.total_input_tokens,
                                    usage_after.total_output_tokens
                                    - usage_before.total_output_tokens,
                                    usage_after.total_cached_input_tokens
                                    - usage_before.total_cached_input_tokens,
                                )
                                claim_elapsed[snapshot.snapshot_id] = (
                                    asyncio.get_running_loop().time() - started
                                )
                    verification_ledger.capture_claims(claim_outcomes)

                    all_claim_results = []
                    reports = []
                    public_verification_by_item = {}
                    items_by_id = {item.id: item for item in important_items}
                    for snapshot, claim_outcome in zip(snapshots, claim_outcomes):
                        usage_before = get_usage_snapshot()
                        claim_results = []
                        budget = ItemVerificationBudget(
                            max_model_calls=(
                                verification_config.max_model_calls_per_item
                            ),
                            used_model_calls=claim_outcome.model_calls,
                        )
                        evidence_started = asyncio.get_running_loop().time()
                        if claim_outcome.status == "ok" and claim_outcome.claims:
                            if claim_client is None:
                                claim_results = [
                                    verification_error_result(claim)
                                    for claim in claim_outcome.claims
                                ]
                            else:
                                verifier = EvidenceVerifier(
                                    claim_client,
                                    max_queries=(
                                        verification_config.max_queries_per_claim
                                    ),
                                    max_documents=(
                                        verification_config.max_documents_per_claim
                                    ),
                                    budget=budget,
                                )
                                remaining = max(
                                    verification_config.timeout_seconds_per_item
                                    - claim_elapsed.get(snapshot.snapshot_id, 0),
                                    0,
                                )
                                completed = 0
                                try:
                                    async with asyncio.timeout(remaining):
                                        for claim in claim_outcome.claims:
                                            claim_results.append(
                                                await verifier.verify(claim, snapshot)
                                            )
                                            completed += 1
                                except TimeoutError:
                                    pending_claims = claim_outcome.claims[completed:]
                                    timeout_duration = max(
                                        asyncio.get_running_loop().time()
                                        - evidence_started
                                        - sum(
                                            result.duration_seconds
                                            for result in claim_results
                                        ),
                                        0,
                                    )
                                    claim_results.extend(
                                        verification_error_result(
                                            claim,
                                            stop_reason="budget",
                                            duration_seconds=(
                                                timeout_duration if index == 0 else 0
                                            ),
                                        )
                                        for index, claim in enumerate(pending_claims)
                                    )

                        all_claim_results.extend(claim_results)
                        item = items_by_id.get(snapshot.item_id)
                        artifact_models = (
                            item.processing.artifacts
                            if item is not None and item.processing is not None
                            else {}
                        )
                        artifacts = (
                            {
                                language: artifact.model_dump(mode="json")
                                for language, artifact in artifact_models.items()
                            }
                            if artifact_models
                            else {}
                        )
                        elapsed = claim_elapsed.get(snapshot.snapshot_id, 0) + (
                            asyncio.get_running_loop().time() - evidence_started
                        )
                        if not artifact_models:
                            audit_outcome = ArtifactAuditOutcome(
                                status="ok",
                                model=self.config.ai.model,
                            )
                        elif claim_client is None:
                            audit_outcome = ArtifactAuditOutcome(
                                status="error",
                                error_code="model_error",
                                model=self.config.ai.model,
                            )
                        else:
                            auditor = ArtifactAuditor(claim_client, budget)
                            audit_calls_before = budget.used_model_calls
                            remaining = max(
                                verification_config.timeout_seconds_per_item
                                - elapsed,
                                0,
                            )
                            try:
                                audit_started = asyncio.get_running_loop().time()
                                async with asyncio.timeout(remaining):
                                    audit_outcome = await auditor.audit(
                                        artifact_models,
                                        claim_results,
                                    )
                            except TimeoutError:
                                audit_outcome = ArtifactAuditOutcome(
                                    status="error",
                                    error_code="timeout",
                                    model=self.config.ai.model,
                                    model_calls=(
                                        budget.used_model_calls - audit_calls_before
                                    ),
                                    duration_seconds=(
                                        asyncio.get_running_loop().time()
                                        - audit_started
                                    ),
                                )
                        usage_after = get_usage_snapshot()
                        claim_input, claim_output, claim_cached_input = (
                            claim_token_usage.get(snapshot.snapshot_id, (0, 0, 0))
                        )
                        token_usage = build_token_usage_report(
                            claim_input
                            + usage_after.total_input_tokens
                            - usage_before.total_input_tokens,
                            claim_output
                            + usage_after.total_output_tokens
                            - usage_before.total_output_tokens,
                            model=self.config.ai.model,
                            cached_input_tokens=(
                                claim_cached_input
                                + usage_after.total_cached_input_tokens
                                - usage_before.total_cached_input_tokens
                            ),
                            input_price_per_million_usd=(
                                verification_config.input_price_per_million_usd
                            ),
                            cached_input_price_per_million_usd=(
                                verification_config.cached_input_price_per_million_usd
                            ),
                            output_price_per_million_usd=(
                                verification_config.output_price_per_million_usd
                            ),
                            quota_name=(
                                "OpenCode Go"
                                if (self.config.ai.base_url or "").startswith(
                                    "https://opencode.ai/zen/go/"
                                )
                                else None
                            ),
                        )
                        reports.append(
                            build_verification_report(
                                run_id=verification_ledger.run_id,
                                selected_snapshot=snapshot,
                                claim_outcome=claim_outcome,
                                claim_results=claim_results,
                                artifacts=artifacts,
                                artifact_audit=audit_outcome,
                                token_usage=token_usage,
                            )
                        )
                        state = (
                            "check_failed"
                            if claim_outcome.status == "error"
                            or (
                                claim_results
                                and all(
                                    result.adjudication.status
                                    == "verification_error"
                                    for result in claim_results
                                )
                            )
                            else "no_claims"
                            if not claim_outcome.claims
                            else "checked"
                        )
                        public_verification_by_item[snapshot.item_id] = (
                            build_public_verification(
                                claim_results,
                                state=state,
                                token_usage=token_usage,
                            )
                        )
                    verification_ledger.capture_verification(
                        all_claim_results,
                        reports,
                    )
                    if verification_config.publish_to_site:
                        for item in important_items:
                            item.metadata["evidence_ledger"] = (
                                public_verification_by_item.get(item.id)
                                or build_public_verification([], state="not_checked")
                            )
                except Exception as verification_error:
                    self.console.print(
                        f"[yellow]{self.icons['warning']} Verification shadow stage "
                        f"failed; publication is unchanged: {verification_error}[/yellow]\n"
                    )

            # 7. Generate and save daily summaries for each configured language
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            for lang in self.config.ai.languages:
                summarizer = DailySummarizer(
                    profile_names=self.profiles.names,
                    profile_order=self.config.digest.profile_order,
                    brand=self.config.digest.brand,
                )
                summary = await summarizer.generate_summary(important_items, today, len(all_items), language=lang)

                # Save to data/summaries/
                summary_path = self.storage.save_daily_summary(today, summary, language=lang)
                self.console.print(
                    f"{self.icons['save']} Saved {lang.upper()} summary to: {summary_path}\n"
                )

                # Publish as a page of the static site. Not guarded: the
                # headline links sent below point at this page.
                article_pages = summarizer.build_article_pages(
                    important_items, today, language=lang
                )
                site_path = self.storage.publish_site_pages(
                    today, article_pages, language=lang
                )
                self.console.print(
                    f"{self.icons['document']} Published {len(article_pages) - 1} "
                    f"{lang.upper()} article pages to the site: {site_path}\n"
                )

                # Index the articles for archive search. Guarded, unlike the
                # site publish: a dead search backend must not stop delivery,
                # the pipeline degrades rather than fails.
                if self.config.search.enabled:
                    try:
                        async with SearchIndexer(self.config.search) as indexer:
                            await indexer.ensure_index()
                            documents = build_search_documents(
                                summarizer.build_view(important_items, lang),
                                today,
                                lang,
                                self.config.search.site_base,
                            )
                            indexed = await indexer.index_documents(documents)
                        self.console.print(
                            f"{self.icons['detail']} Indexed {indexed} "
                            f"{lang.upper()} articles for search\n"
                        )
                    except Exception as search_error:
                        self.console.print(
                            f"{self.icons['warning']} Search indexing failed, "
                            f"continuing without it: {search_error}\n"
                        )

                # Send email if configured
                if self.email_manager and self.config.email and self.config.email.enabled:
                    self.console.print(
                        f"{self.icons['email']} Sending {lang.upper()} email summary..."
                    )
                    subscribers = self.storage.load_subscribers()
                    subject = f"Horizon Summary ({lang.upper()}) - {today}"
                    self.email_manager.send_daily_summary(summary, subject, subscribers)

                # Send webhook notification if configured
                if self.webhook_notifier:
                    await self.webhook_notifier.send_daily_summary(
                        summary=summary,
                        important_items=important_items,
                        all_items_count=len(all_items),
                        date=today,
                        lang=lang,
                        summarizer=summarizer,
                    )

            self.console.print(
                f"[bold green]{self.icons['success']} "
                "Horizon completed successfully![/bold green]"
            )
            usage = get_usage_snapshot()
            if usage.total_tokens > 0:
                self.console.print(
                    f"\n{self.icons['tokens']} Token usage this run: "
                    f"{usage.total_tokens} tokens "
                    f"(input: {usage.total_input_tokens}, output: {usage.total_output_tokens})"
                )
                for provider, u in sorted(usage.per_provider.items()):
                    if u.total <= 0:
                        continue
                    self.console.print(
                        f"   {self.icons['detail']} {provider}: {u.total} tokens "
                        f"(in: {u.input_tokens}, out: {u.output_tokens})"
                    )

        except Exception as e:
            self.console.print(
                f"[bold red]{self.icons['error']} Error: {e}[/bold red]"
            )

            # Send webhook failure notification if configured
            if self.webhook_notifier:
                await self.webhook_notifier.send_failure(
                    date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    error_message=str(e),
                )

            raise

    def _determine_time_window(self, force_hours: int = None) -> datetime:
        if force_hours:
            since = datetime.now(timezone.utc) - timedelta(hours=force_hours)
        else:
            hours = self.config.collection.time_window_hours
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
        return since

    async def fetch_all_sources(self, since: datetime) -> List[ContentItem]:
        """Fetch content from all configured sources.

        This is a stable stage entry point for integrations such as MCP.

        Args:
            since: Fetch items published after this time

        Returns:
            List[ContentItem]: All fetched items
        """
        self.last_fetch_report = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = []

            # GitHub sources
            if self.config.sources.github:
                github_scraper = GitHubScraper(self.config.sources.github, client)
                tasks.append(self._fetch_with_progress("GitHub", github_scraper, since))

            # Hacker News
            if self.config.sources.hackernews.enabled:
                hn_scraper = HackerNewsScraper(self.config.sources.hackernews, client)
                tasks.append(self._fetch_with_progress("Hacker News", hn_scraper, since))

            # RSS feeds
            if self.config.sources.rss:
                from .extractors import ExtractorRegistry
                rss_scraper = RSSScraper(
                    self.config.sources.rss,
                    client,
                    ExtractorRegistry(self.config.extractors),
                )
                tasks.append(self._fetch_with_progress("RSS Feeds", rss_scraper, since))

            # Reddit
            if self.config.sources.reddit.enabled:
                reddit_scraper = RedditScraper(self.config.sources.reddit, client)
                tasks.append(self._fetch_with_progress("Reddit", reddit_scraper, since))

            # Telegram
            if self.config.sources.telegram.enabled:
                telegram_scraper = TelegramScraper(self.config.sources.telegram, client)
                tasks.append(self._fetch_with_progress("Telegram", telegram_scraper, since))

            # Twitter (Apify or Playwright mode)
            if self.config.sources.twitter and self.config.sources.twitter.enabled:
                tw_cfg = self.config.sources.twitter
                if tw_cfg.mode == "playwright":
                    twitter_scraper = TwitterPlaywrightScraper(tw_cfg)
                else:
                    twitter_scraper = TwitterScraper(tw_cfg, client)
                tasks.append(self._fetch_with_progress("Twitter", twitter_scraper, since))

            # OpenBB (financial news / filings via the OpenBB Platform SDK)
            if self.config.sources.openbb and self.config.sources.openbb.enabled:
                openbb_scraper = OpenBBScraper(self.config.sources.openbb, client)
                tasks.append(self._fetch_with_progress("OpenBB", openbb_scraper, since))

            # OSS Insight trending repos
            if self.config.sources.ossinsight and self.config.sources.ossinsight.enabled:
                oss_scraper = OSSInsightScraper(self.config.sources.ossinsight, client)
                tasks.append(self._fetch_with_progress("OSS Insight", oss_scraper, since))

            # GDELT 2.0 DOC API (key-less global news)
            for index, gdelt_config in enumerate(self.config.sources.gdelt, start=1):
                if gdelt_config.enabled:
                    gdelt_scraper = GDELTScraper(gdelt_config, client)
                    tasks.append(
                        self._fetch_with_progress(
                            f"GDELT {index}", gdelt_scraper, since
                        )
                    )

            # Google News RSS (key-less news search)
            for index, google_news_config in enumerate(
                self.config.sources.google_news, start=1
            ):
                if google_news_config.enabled:
                    gn_scraper = GoogleNewsScraper(google_news_config, client)
                    tasks.append(
                        self._fetch_with_progress(
                            f"Google News {index}", gn_scraper, since
                        )
                    )

            # YouTube channels (RSS discovery + yt-dlp subtitle transcripts).
            # In sidecar mode the work happened in a separate `horizon-video`
            # process, so this host reads an inbox file and needs no channels.
            video_cfg = self.config.sources.video
            if video_cfg.enabled and (video_cfg.channels or video_cfg.mode == "sidecar"):
                video_scraper = VideoScraper(video_cfg, client, self.config.ai)
                tasks.append(self._fetch_with_progress("YouTube", video_scraper, since))

            # Fetch all concurrently
            outcomes = await asyncio.gather(*tasks)
            self.last_fetch_report = FetchReport(outcomes=list(outcomes))

            # Flatten successful and empty outcomes; failures remain in the report.
            all_items: List[ContentItem] = []
            for outcome in outcomes:
                all_items.extend(outcome.items)

            return all_items

    async def _fetch_with_progress(
        self, name: str, scraper, since: datetime
    ) -> SourceFetchOutcome:
        """Fetch from a scraper with progress indication.

        Args:
            name: Source name for display
            scraper: Scraper instance
            since: Fetch items after this time

        Returns:
            SourceFetchOutcome: Named fetch result and diagnostics
        """
        self.console.print(f"{self.icons['fetch']} Fetching from {name}...")
        try:
            items = await scraper.fetch(since)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.console.print(f"[red]   Failed to fetch {name}: {error}[/red]")
            return SourceFetchOutcome(
                source_name=name,
                status="failure",
                error=error,
            )

        self.console.print(f"   Found {len(items)} items from {name}")

        # Show per-sub-source breakdown when there are multiple sub-sources
        sub_counts: Dict[str, int] = defaultdict(int)
        for item in items:
            sub_counts[self._sub_source_label(item)] += 1
        if len(sub_counts) > 1:
            for sub, count in sorted(sub_counts.items()):
                self.console.print(f"      {self.icons['detail']} {sub}: {count}")

        return SourceFetchOutcome(
            source_name=name,
            status="success" if items else "empty",
            items=items,
        )

    @staticmethod
    def _sub_source_label(item: ContentItem) -> str:
        """Return a human-readable sub-source label for an item."""
        meta = item.metadata
        if meta.get("subreddit"):
            return f"r/{meta['subreddit']}"
        if meta.get("feed_name"):
            return meta["feed_name"]
        if meta.get("channel"):
            return f"@{meta['channel']}"
        if meta.get("period") and meta.get("repo"):
            return f"ossinsight:{meta.get('primary_language', 'all')}"
        if meta.get("repo"):
            return meta["repo"]
        if meta.get("watchlist"):
            return meta["watchlist"]
        if meta.get("source_name"):
            return meta["source_name"]
        if meta.get("gn_query"):
            return f"google_news:{meta['gn_query']}"
        if meta.get("domain"):
            return meta["domain"]
        return item.author or "unknown"

    def merge_cross_source_duplicates(
        self,
        items: List[ContentItem],
        *,
        member_map: Optional[Dict[str, List[str]]] = None,
    ) -> List[ContentItem]:
        """Merge items that point to the same URL from different sources.

        This is a stable stage helper for integrations such as MCP.

        Keeps the item with the richest content and combines metadata.

        Args:
            items: Items to deduplicate

        Returns:
            List[ContentItem]: Deduplicated items
        """
        if member_map is not None:
            for item in items:
                member_map.pop(item.id, None)

        # Group by normalized URL
        url_groups: Dict[tuple[object, ...], List[ContentItem]] = {}
        for item in items:
            if isinstance(item.profile, list):
                requested_profile: object = tuple(
                    profile_id.strip() for profile_id in item.profile
                )
            else:
                requested_profile = (item.profile or "auto").strip() or "auto"
            key = (*_deduplication_url_key(str(item.url)), requested_profile)
            url_groups.setdefault(key, []).append(item)

        merged = []
        for group in url_groups.values():
            group_copies = [item.model_copy(deep=True) for item in group]
            if len(group) == 1:
                merged.append(group_copies[0])
                if member_map is not None:
                    member_map[group_copies[0].id] = [group[0].id]
                continue

            # Pick the item with the richest content as primary
            primary = max(group_copies, key=lambda x: len(x.content or ""))

            # Merge metadata and source info from other items
            all_sources = []
            for item in group_copies:
                if item.source_type.value not in all_sources:
                    all_sources.append(item.source_type.value)
                # Merge metadata (engagement, discussion, etc.)
                for mk, mv in item.metadata.items():
                    if mk not in primary.metadata or not primary.metadata[mk]:
                        primary.metadata[mk] = mv

                # Append content (e.g., comments from another source)
                if item is not primary and item.content:
                    if primary.content and item.content not in primary.content:
                        primary.content = (primary.content or "") + f"\n\n--- From {item.source_type.value} ---\n" + item.content

            primary.metadata["merged_sources"] = all_sources
            merged.append(primary)
            if member_map is not None:
                member_map[primary.id] = list(dict.fromkeys(item.id for item in group))

        return merged

    async def merge_topic_duplicates(
        self,
        items: List[ContentItem],
        *,
        log: bool = True,
        member_map: Optional[Dict[str, List[str]]] = None,
    ) -> List[ContentItem]:
        """Merge items covering the same topic using AI semantic deduplication.

        This is a stable stage helper for integrations such as MCP.

        Sends all item titles, tags, and summaries to AI in a single call.
        Items must already be sorted by analysis score descending so that the first
        item in each duplicate group is always the highest-scored one.
        Content (comments) from duplicate items is merged into the primary.

        Falls back to returning items unchanged if the AI call fails.
        """
        lineage = {item.id: [item.id] for item in items}

        def with_lineage(result: List[ContentItem]) -> List[ContentItem]:
            if member_map is not None:
                for item in items:
                    member_map.pop(item.id, None)
                for survivor in result:
                    member_map[survivor.id] = list(
                        dict.fromkeys(lineage.get(survivor.id, [survivor.id]))
                    )
            return result

        if len(items) <= 1:
            return with_lineage(items)

        from .ai.prompting.deduplication import TOPIC_DEDUP_SYSTEM, TOPIC_DEDUP_USER
        from .ai.utils import parse_json_response

        # Build the item list for the prompt
        lines = []
        for i, item in enumerate(items):
            analysis = item.processing.analysis if item.processing else None
            tags = ", ".join(analysis.tags) if analysis and analysis.tags else "—"
            summary = analysis.summary if analysis else "—"
            lines.append(f"[{i}] {item.title}\n    Tags: {tags}\n    Summary: {summary}")
        items_text = "\n\n".join(lines)

        try:
            ai_client = create_ai_client(self.config.ai)
            response = await ai_client.complete(
                system=TOPIC_DEDUP_SYSTEM,
                user=TOPIC_DEDUP_USER.format(items=items_text),
            )
            result = parse_json_response(response)
            if result is None:
                if log:
                    self.console.print("[yellow]  dedup: could not parse AI response, skipping[/yellow]")
                return with_lineage(items)

            duplicate_groups = result.get("duplicates", [])
        except Exception as e:
            if log:
                self.console.print(f"[yellow]  dedup: AI call failed ({e}), skipping[/yellow]")
            return with_lineage(items)

        if not duplicate_groups:
            return with_lineage(items)

        # Build a set of indices to drop (all non-primary duplicates)
        drop_indices: set[int] = set()
        for group in duplicate_groups:
            if not isinstance(group, list) or len(group) < 2:
                continue
            primary_idx = group[0]
            # isinstance guard mirrors the one on dup_idx below. These indices
            # come from model output: a quoted "0" would raise TypeError here,
            # outside any handler, killing a run whose analysis is already paid
            # for.
            if (
                not isinstance(primary_idx, int)
                or primary_idx < 0
                or primary_idx >= len(items)
            ):
                continue
            primary = items[primary_idx]
            for dup_idx in group[1:]:
                if not isinstance(dup_idx, int) or dup_idx < 0 or dup_idx >= len(items):
                    continue
                if dup_idx == primary_idx:
                    continue
                dup = items[dup_idx]
                # Merge comments/content from the duplicate into the primary
                if dup.content:
                    if not primary.content or dup.content not in primary.content:
                        label = dup.source_type.value
                        primary.content = (primary.content or "") + f"\n\n--- From {label} ---\n{dup.content}"
                lineage[primary.id].extend(lineage.get(dup.id, [dup.id]))
                if log:
                    self.console.print(
                        f"   [dim]dedup: keep [{primary_idx}] {primary.title}[/dim]\n"
                        f"   [dim]       drop [{dup_idx}] {dup.title}[/dim]"
                    )
                drop_indices.add(dup_idx)

        return with_lineage(
            [item for i, item in enumerate(items) if i not in drop_indices]
        )

    async def filter_items(
        self,
        items: List[ContentItem],
        *,
        threshold: Optional[float] = None,
        topic_dedup: bool = True,
        apply_balance: bool = True,
        log: bool = True,
        topic_member_map: Optional[Dict[str, List[str]]] = None,
    ) -> FilteringPipelineResult:
        """Apply score thresholding, optional topic dedup, and digest balancing."""
        threshold_items = []
        for item in items:
            if self.passes_profile_filter(item, threshold):
                threshold_items.append(item)
        threshold_items.sort(
            key=lambda item: (
                item.processing.analysis.score
                if item.processing and item.processing.analysis and item.processing.analysis.score is not None
                else -1
            ),
            reverse=True,
        )

        if log:
            self.console.print(
                f"{self.icons['filter']} Selected {len(threshold_items)} items "
                "with profile filters\n"
            )

        deduped_items = threshold_items
        if topic_member_map is not None:
            for item in threshold_items:
                topic_member_map[item.id] = [item.id]
        if topic_dedup and deduped_items:
            profile_groups: Dict[str, List[ContentItem]] = defaultdict(list)
            for item in deduped_items:
                profile_id = (
                    item.processing.classification.profile
                    if item.processing
                    else self.profiles.default_profile
                )
                profile_groups[profile_id].append(item)
            deduped_items = []
            for profile_id, profile_items in profile_groups.items():
                settings = self.config.processing.profile_settings.get(profile_id)
                if settings is None or settings.topic_dedup:
                    if topic_member_map is None:
                        merged_profile_items = await self.merge_topic_duplicates(
                            profile_items, log=log
                        )
                    else:
                        merged_profile_items = await self.merge_topic_duplicates(
                            profile_items,
                            log=log,
                            member_map=topic_member_map,
                        )
                    deduped_items.extend(merged_profile_items)
                else:
                    deduped_items.extend(profile_items)
            deduped_items.sort(
                key=lambda item: (
                    item.processing.analysis.score
                    if item.processing
                    and item.processing.analysis
                    and item.processing.analysis.score is not None
                    else -1
                ),
                reverse=True,
            )
        topic_dedup_removed = len(threshold_items) - len(deduped_items)

        if log and topic_dedup_removed:
            self.console.print(
                f"{self.icons['cleanup']} Removed {topic_dedup_removed} topic duplicates "
                f"→ {len(deduped_items)} unique items\n"
            )

        balanced_digest = (
            self.apply_balanced_digest(deduped_items, log=log)
            if apply_balance
            else BalancedDigestResult(items=deduped_items)
        )
        return FilteringPipelineResult(
            items=balanced_digest.items,
            threshold_count=len(threshold_items),
            topic_dedup_count=len(deduped_items),
            topic_dedup_removed=topic_dedup_removed,
            balanced_digest=balanced_digest,
        )

    async def select_digest_items(
        self,
        items: List[ContentItem],
        *,
        threshold: Optional[float] = None,
        topic_dedup: bool = True,
        log: bool = True,
        topic_member_map: Optional[Dict[str, List[str]]] = None,
    ) -> FilteringPipelineResult:
        """Select final digest items using the same stages for every entry point."""
        initial = await self.filter_items(
            items,
            threshold=threshold,
            topic_dedup=topic_dedup,
            apply_balance=False,
            log=log,
            topic_member_map=topic_member_map,
        )
        candidates = initial.items
        await self._expand_twitter_discussion(candidates)

        # Targeted re-analysis can lower a score, so reapply profile filters.
        eligible = [
            item
            for item in candidates
            if self.passes_profile_filter(item, threshold)
        ]
        eligible.sort(
            key=lambda item: (
                item.processing.analysis.score
                if item.processing
                and item.processing.analysis
                and item.processing.analysis.score is not None
                else -1
            ),
            reverse=True,
        )
        balanced = self.apply_balanced_digest(eligible, log=log)
        return FilteringPipelineResult(
            items=balanced.items,
            threshold_count=initial.threshold_count,
            topic_dedup_count=initial.topic_dedup_count,
            topic_dedup_removed=initial.topic_dedup_removed,
            balanced_digest=balanced,
            eligible_count=len(eligible),
        )

    def passes_profile_filter(
        self,
        item: ContentItem,
        threshold: Optional[float] = None,
    ) -> bool:
        if not item.processing or not item.processing.analysis:
            return False
        profile_id = item.processing.classification.profile
        settings = self.config.processing.profile_settings.get(profile_id)
        effective_threshold = threshold
        if effective_threshold is None and settings is not None:
            effective_threshold = settings.threshold
        if effective_threshold is None:
            # Fail open, but say so. A profile with no profile_settings entry
            # otherwise admits every item regardless of score — including 1/10 —
            # and each one is then enriched at full cost with nothing in the log
            # to explain where they came from.
            # setdefault, not attribute access: several tests build this class
            # with __new__ and never run __init__.
            warned = self.__dict__.setdefault("_thresholdless_profiles", set())
            if settings is None and profile_id not in warned:
                warned.add(profile_id)
                self.console.print(
                    f"[yellow]{self.icons['warning']} Profile '{profile_id}' has no "
                    "processing.profile_settings entry, so it has no score threshold: "
                    "every item it classifies reaches the digest and is enriched at "
                    "full cost. Add a threshold to filter it.[/yellow]"
                )
            return True
        score = item.processing.analysis.score
        return score is not None and score >= effective_threshold

    def apply_balanced_digest(
        self,
        items: List[ContentItem],
        *,
        log: bool = True,
    ) -> BalancedDigestResult:
        """Apply configured category quotas and the final item cap.

        Categories are read from ``item.metadata["category"]``. If a category
        appears in more than one configured group, the first group in config
        order wins.
        """
        digest = self.config.digest
        groups = digest.category_groups
        max_items = digest.max_items

        if not groups and max_items is None:
            return BalancedDigestResult(items=items)

        sorted_items = sorted(
            items,
            key=lambda item: (
                item.processing.analysis.score
                if item.processing and item.processing.analysis and item.processing.analysis.score is not None
                else -1
            ),
            reverse=True,
        )

        category_to_group: Dict[str, str] = {}
        duplicate_categories: List[str] = []
        for group_key, group in groups.items():
            for category in group.categories:
                if category in category_to_group:
                    if category_to_group[category] != group_key:
                        duplicate_categories.append(category)
                    continue
                category_to_group[category] = group_key

        if log:
            for category in sorted(set(duplicate_categories)):
                first_group = category_to_group[category]
                self.console.print(
                    f"[yellow]Warning: category '{category}' is configured in multiple "
                    f"groups; using '{first_group}'.[/yellow]"
                )

        selected: List[tuple[ContentItem, str]] = []
        group_counts: Dict[str, int] = defaultdict(int)
        default_group = digest.default_group

        for item in sorted_items:
            category = item.metadata.get("category")
            group_key = (
                category_to_group.get(category, default_group)
                if isinstance(category, str)
                else default_group
            )

            if group_key in groups:
                limit = groups[group_key].limit
            else:
                limit = digest.default_group_limit

            if limit is not None and group_counts[group_key] >= limit:
                continue

            selected.append((item, group_key))
            group_counts[group_key] += 1

        if max_items is not None:
            selected = selected[:max_items]

        final_counts: Dict[str, int] = defaultdict(int)
        for _, group_key in selected:
            final_counts[group_key] += 1

        group_limits: Dict[str, Optional[int]] = {
            group_key: group.limit for group_key, group in groups.items()
        }
        group_limits.setdefault(default_group, digest.default_group_limit)

        if log:
            self.console.print(
                f"{self.icons['balance']} Balanced digest selected "
                f"{len(selected)}/{len(items)} items"
            )
            for group_key, group in groups.items():
                label = group.name or group_key
                self.console.print(
                    f"      {self.icons['detail']} {label}: "
                    f"{final_counts.get(group_key, 0)}/{group.limit}"
                )
            if (
                final_counts.get(default_group, 0)
                or digest.default_group_limit is not None
            ):
                limit_label = (
                    str(digest.default_group_limit)
                    if digest.default_group_limit is not None
                    else "unlimited"
                )
                self.console.print(
                    f"      {self.icons['detail']} {default_group}: "
                    f"{final_counts.get(default_group, 0)}/{limit_label}"
                )
            self.console.print("")

        return BalancedDigestResult(
            items=[item for item, _ in selected],
            enabled=True,
            group_counts=dict(final_counts),
            group_limits=group_limits,
            duplicate_categories=sorted(set(duplicate_categories)),
        )

    async def _expand_twitter_discussion(self, items: List[ContentItem]) -> None:
        """Second-stage: fetch reply text for important Twitter items and re-analyze.

        Only runs when sources.twitter.fetch_reply_text is True.
        Bounded by max_tweets_to_expand to control cost.
        """
        tw_cfg = self.config.sources.twitter
        if not tw_cfg or not tw_cfg.enabled or not tw_cfg.fetch_reply_text:
            return

        from .models import SourceType

        twitter_items = [
            item for item in items
            if item.source_type == SourceType.TWITTER
        ][:tw_cfg.max_tweets_to_expand]

        if not twitter_items:
            return

        self.console.print(
            f"{self.icons['discussion']} Fetching reply text for "
            f"{len(twitter_items)} Twitter items..."
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            if tw_cfg.mode == "playwright":
                self.console.print(
                    "   [yellow]Reply expansion not yet supported in Playwright mode.[/yellow]"
                )
                return
            scraper = TwitterScraper(tw_cfg, client)
            expanded = []
            for item in twitter_items:
                try:
                    reply_lines = await scraper.fetch_replies_for_item(item)
                    if TwitterScraper.append_discussion_content(item, reply_lines):
                        expanded.append(item)
                        self.console.print(
                            f"   {self.icons['discussion']} {len(reply_lines)} replies "
                            f"added to: {item.title[:60]}"
                        )
                except Exception as exc:
                    self.console.print(
                        f"   [yellow]{self.icons['warning']} Reply fetch failed for "
                        f"{item.id}: {exc}[/yellow]"
                    )

        if not expanded:
            return

        self.console.print(
            f"   Re-analyzing {len(expanded)} Twitter items with reply context...\n"
        )
        ai_client = create_ai_client(self.config.ai)
        analyzer = ContentAnalyzer(ai_client, self.profiles, console=self.console)
        await analyzer.analyze_batch(expanded)

    async def enrich_items(self, items: List[ContentItem]) -> EnrichmentBatchResult:
        """Enrich items with background knowledge (2nd AI pass).

        For each item that passed the score threshold, call AI to generate
        background knowledge based on the item's actual content.

        Args:
            items: Important items to enrich (modified in-place)
        """
        if not items:
            return EnrichmentBatchResult()

        self.console.print(
            f"{self.icons['enrich']} Enriching with background knowledge..."
        )
        ai_client = create_ai_client(self.config.ai)
        enricher = ContentEnricher(
            ai_client,
            self.profiles,
            self.config.ai.languages,
            console=self.console,
        )
        result = await enricher.enrich_batch(items)
        self.console.print(
            f"   Enriched {result.succeeded_count}/{len(items)} items"
        )
        if result.failed_count:
            self.console.print(
                f"   [yellow]Skipped {result.failed_count} items after enrichment "
                f"failed: {', '.join(result.failed_ids)}[/yellow]"
            )
        self.console.print("")
        return result

    async def analyze_items(self, items: List[ContentItem]) -> List[ContentItem]:
        """Analyze content items with AI.

        Args:
            items: Items to analyze

        Returns:
            List[ContentItem]: Analyzed items
        """
        self.console.print(f"{self.icons['ai']} Analyzing content with AI...")

        ai_client = create_ai_client(self.config.ai)
        analyzer = ContentAnalyzer(ai_client, self.profiles, console=self.console)

        return await analyzer.analyze_batch(items)
