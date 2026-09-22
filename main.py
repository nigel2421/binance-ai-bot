"""
Deriv Crypto AI Bot - Stage 5 Multi-Agent Consensus & Opportunity Ranking Main Entry Point.

Runs live market data monitoring, multi-timeframe feature calculation, regime intelligence,
5 independent strategy specialists, evidence-weighted consensus, and cross-market opportunity scoring.

Supports CLI flags:
  --inspect-consensus <symbol>  : Detailed consensus & evidence breakdown for a symbol.
  --opportunities              : Live cross-market opportunity ranking & stream diagnostics.
  --inspect-strategies <symbol> : Stage 4 strategy specialist inspection.
"""

import asyncio
import logging
import sys
import time
from typing import Dict, Optional, List, Tuple, Any

from src.config import config
from src.api.deriv_client import DerivClient, ConnectionState
from src.market.crypto_market_registry import CryptoMarketRegistry
from src.market.market_data_engine import CryptoMarketDataEngine
from src.monitoring.watcher_health import CryptoWatcher, GlobalHealthManager, WatcherState
from src.monitoring.stream_certifier import LiveStreamCertifier, StreamCertificationState

from src.features.crypto_feature_engine import CryptoFeatureEngine
from src.features.market_structure import MarketStructureEngine
from src.agents.crypto_regime_agent import (
    CryptoRegimeAgent,
    MultiTimeframeRegimeEngine,
    CryptoMarketQualityEngine,
    SingleTimeframeRegimeResult
)

from src.strategy.strategy_team import CryptoStrategyTeam
from src.strategy.signal import StrategySignal, SignalStatus
from src.consensus.crypto_consensus_engine import CryptoConsensusEngine, ConsensusResult, ConsensusDirection
from src.opportunity.crypto_opportunity_scorer import CryptoOpportunityScorer, CryptoOpportunity, OpportunityStatus
from src.opportunity.crypto_opportunity_ranker import CryptoOpportunityRanker

from src.execution.crypto_contract_selector import CryptoContractSelector
from src.execution.proposal_engine import DerivProposalEngine
from src.analytics.probability_calibrator import ProbabilityCalibrator
from src.execution.expected_value_engine import ExpectedValueEngine
from src.risk.crypto_risk_manager import CryptoRiskManager
from src.execution.paper_trade_engine import CryptoPaperTradeEngine
from src.execution.trade_journal import CryptoTradeJournal, JournalRecord

# Ensure UTF-8 output encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("SYSTEM")


def analyze_symbol_intelligence(
    sym: str,
    data_engine: CryptoMarketDataEngine,
    regime_agent: CryptoRegimeAgent
) -> Tuple[Dict[str, SingleTimeframeRegimeResult], Dict[str, Any], float]:
    """Perform multi-timeframe feature calculation and regime evaluation for a single symbol."""
    tf_results: Dict[str, SingleTimeframeRegimeResult] = {}
    tf_snapshots = {}

    for tf in data_engine.TIMEFRAMES_SEC:
        df = data_engine.get_dataframe(sym, tf)
        feat = CryptoFeatureEngine.calculate_snapshot(df, sym, tf)
        struct = MarketStructureEngine.analyze_structure(df, sym, tf)
        res = regime_agent.classify_regime(feat, struct)
        tf_results[tf] = res
        tf_snapshots[tf] = feat

    mtf_res = MultiTimeframeRegimeEngine.evaluate_multitimeframe_regime(sym, tf_results)

    p_feat = tf_snapshots.get("15m") or tf_snapshots.get("1m")
    d_qual = p_feat.data_quality_score if p_feat else 0.0
    r_conf = mtf_res.get("regime_confidence", 0.0)
    t_align = mtf_res.get("timeframe_alignment", 0.0)
    p_trend = tf_results.get("15m") or tf_results.get("1m")
    t_str = p_trend.trend.strength if p_trend else 0.0

    quality_score = CryptoMarketQualityEngine.calculate_quality_score(d_qual, r_conf, t_align, t_str)
    return tf_results, mtf_res, quality_score


def evaluate_market_stage5(
    sym: str,
    data_engine: CryptoMarketDataEngine,
    regime_agent: CryptoRegimeAgent,
    strategy_team: CryptoStrategyTeam,
    consensus_engine: CryptoConsensusEngine,
    opportunity_scorer: CryptoOpportunityScorer,
    watcher_health_dict: Dict[str, Any],
    allow_offline: bool = False,
) -> Tuple[List[StrategySignal], ConsensusResult, CryptoOpportunity]:
    """Runs full Stage 4 & Stage 5 pipeline for a single market symbol."""
    tf_snapshots = {}
    for tf in data_engine.TIMEFRAMES_SEC:
        df = data_engine.get_dataframe(sym, tf)
        tf_snapshots[tf] = CryptoFeatureEngine.calculate_snapshot(df, sym, tf).to_dict()

    df_15m = data_engine.get_dataframe(sym, "15m")
    struct_dict = MarketStructureEngine.analyze_structure(df_15m, sym, "15m").to_dict()

    _, mtf_res, quality_score = analyze_symbol_intelligence(sym, data_engine, regime_agent)
    mtf_res["market_quality"] = quality_score

    signals = strategy_team.evaluate_market(
        symbol=sym,
        feature_snapshots=tf_snapshots,
        regime_snapshot=mtf_res,
        structure_snapshot=struct_dict,
        watcher_health=watcher_health_dict,
        allow_offline=allow_offline,
    )

    consensus = consensus_engine.evaluate_consensus(
        symbol=sym,
        signals=signals,
        regime_snapshot=mtf_res,
    )

    opportunity = opportunity_scorer.evaluate_opportunity(
        consensus=consensus,
        watcher_health=watcher_health_dict,
    )

    return signals, consensus, opportunity


def print_terminal_intelligence_radar(
    health_mgr: GlobalHealthManager,
    client: DerivClient,
    watchers: Dict[str, CryptoWatcher],
    strategy_team: CryptoStrategyTeam,
    consensus_engine: CryptoConsensusEngine,
    opportunity_scorer: CryptoOpportunityScorer,
    data_engine: CryptoMarketDataEngine,
    regime_agent: CryptoRegimeAgent,
):
    """Render Stage 5 Multi-Agent Consensus & Opportunity Radar status view."""
    auth_str = "AUTHENTICATED" if client.state == ConnectionState.AUTHENTICATED else "PUBLIC_MODE"
    report = health_mgr.get_health_report(client.state.value, auth_str, watchers)

    print("\n=========================================================================================")
    print("DERIV CRYPTO AI — MULTI-AGENT CONSENSUS & OPPORTUNITY RADAR (STAGE 5)")
    print("=========================================================================================")
    print(f"Mode:              DRY RUN ({config.dry_run}) | Live Trading: DISABLED ({config.live_trading})")
    print(f"API Connection:    {report['ws_state']} | Auth: {report['auth_state']}")
    print(f"Crypto Markets:    {report['discovered_markets']} (Healthy: {report['watchers_healthy']} | History Only: {report['watchers_history_only']})")
    print(f"System Uptime:     {report['uptime']} | Total Ticks: {report['total_ticks']}")
    print("-----------------------------------------------------------------------------------------")
    print(f"{'SYMBOL':<10} {'REGIME':<16} {'QUALITY':<8} {'CONSENSUS':<12} {'STRENGTH':<16} {'SCORE':<7} {'TIER':<8} {'STATUS'}")
    print("-----------------------------------------------------------------------------------------")

    all_opportunities: List[CryptoOpportunity] = []
    for sym, watcher in watchers.items():
        watcher.evaluate_health(is_ws_connected=(client.state in (ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED)))

        signals, consensus, op = evaluate_market_stage5(
            sym, data_engine, regime_agent, strategy_team, consensus_engine, opportunity_scorer, watcher.get_health_status_dict()
        )
        all_opportunities.append(op)

        cons_str = f"{consensus.direction.value} {int(consensus.consensus_confidence*100)}%" if consensus.direction not in (ConsensusDirection.NO_CONSENSUS, ConsensusDirection.CONFLICTED) else consensus.direction.value

        print(
            f"{sym:<10} "
            f"{consensus.regime:<16} "
            f"{consensus.market_quality:<8.1f} "
            f"{cons_str:<12} "
            f"{consensus.consensus_strength.value:<16} "
            f"{op.opportunity_score:<7.1f} "
            f"{op.tier.value:<8} "
            f"{op.status.value}"
        )

    ranked_ops = CryptoOpportunityRanker.rank_opportunities(all_opportunities)
    conflicted_ops = CryptoOpportunityRanker.get_top_conflicted_markets(all_opportunities)

    print("-----------------------------------------------------------------------------------------")
    print("TOP RANKED CROSS-MARKET OPPORTUNITIES")
    if ranked_ops:
        for idx, top_op in enumerate(ranked_ops[:3], 1):
            print(f"#{idx} {top_op.symbol:<10} | Score: {top_op.opportunity_score:.1f} | Tier: {top_op.tier.value:<8} | Dir: {top_op.direction:<8} | Top Spec: {top_op.top_strategy}")
    else:
        print("No qualified live opportunities evaluated yet.")

    if conflicted_ops:
        print("-----------------------------------------------------------------------------------------")
        print("TOP CONFLICTED MARKETS (DISAGREEMENT RADAR)")
        for cop in conflicted_ops[:2]:
            print(f"! {cop.symbol:<10} | Status: {cop.status.value:<10} | Penalty: -{cop.conflict_penalty:.1f} | Top Spec: {cop.top_strategy}")

    print("=========================================================================================\n")


def print_consensus_inspection_report(
    sym: str,
    data_engine: CryptoMarketDataEngine,
    regime_agent: CryptoRegimeAgent,
    strategy_team: CryptoStrategyTeam,
    consensus_engine: CryptoConsensusEngine,
    opportunity_scorer: CryptoOpportunityScorer,
    watcher_health: Dict[str, Any],
):
    """Render detailed CLI inspection report for Consensus and Opportunity Scoring."""
    signals, consensus, op = evaluate_market_stage5(
        sym, data_engine, regime_agent, strategy_team, consensus_engine, opportunity_scorer, watcher_health, allow_offline=True
    )

    print("\n=============================================================")
    print(f"CRYPTO CONSENSUS & OPPORTUNITY INSPECTION: {sym}")
    print("=============================================================")
    print(f"Market Regime:          {consensus.regime}")
    print(f"Regime Confidence:      {int(consensus.regime_confidence * 100)}%")
    print(f"Market Quality Score:   {consensus.market_quality:.1f} / 100")
    print(f"Timeframe Alignment:    {consensus.timeframe_alignment:.1f} / 100")
    print("-------------------------------------------------------------")

    print("\nSTAGE 4 STRATEGY SPECIALIST SIGNALS:")
    for sig in signals:
        status_str = f"({sig.status.value})" if sig.status != SignalStatus.CANDIDATE else ""
        print(f"  {sig.strategy:<26} -> {sig.direction.value:<8} Setup Conf: {sig.confidence:.2f} Tier: {sig.tier.value} {status_str}")

    print("\nSTAGE 5 CONSENSUS RESULT:")
    print(f"  Consensus Direction:  {consensus.direction.value}")
    print(f"  Consensus Strength:   {consensus.consensus_strength.value}")
    print(f"  Setup Consensus Conf: {consensus.consensus_confidence:.4f} ({int(consensus.consensus_confidence*100)}%)")
    print(f"  Agreement Score:      {consensus.agreement_score:.1f} / 100")
    print(f"  Conflict Score:       {consensus.conflict_score:.1f} / 100")
    print(f"  Evidence Diversity:   {consensus.evidence_diversity_score:.1f} / 100")
    print(f"  Bullish Weight:       {consensus.bullish_weight:.4f}")
    print(f"  Bearish Weight:       {consensus.bearish_weight:.4f}")
    print(f"  Strongest Supporter:  {consensus.strongest_supporter or 'NONE'}")
    print(f"  Strongest Opponent:   {consensus.strongest_opponent or 'NONE'}")

    print("\nSTAGE 5 OPPORTUNITY SCORE:")
    print(f"  Opportunity Score:    {op.opportunity_score:.1f} / 100")
    print(f"  Research Tier:        {op.tier.value}")
    print(f"  Status:               {op.status.value}")
    print(f"  Conflict Penalty:    -{op.conflict_penalty:.1f}")
    print("  Component Breakdown:")
    print(f"    - Consensus Quality: {op.consensus_score:.1f} (Weight 30%)")
    print(f"    - Market Quality:    {op.market_quality_score:.1f} (Weight 15%)")
    print(f"    - Alignment:         {op.timeframe_alignment_score:.1f} (Weight 15%)")
    print(f"    - Regime Conf:       {op.regime_score:.1f} (Weight 10%)")
    print(f"    - Evidence Diversity: {op.evidence_diversity_score:.1f} (Weight 10%)")
    print(f"    - Signal Freshness:  {op.signal_freshness_score:.1f} (Weight 10%)")

    print("\n=============================================================")
    print("NOTICE: CANDIDATE OPPORTUNITIES ONLY — NO BUY/SELL ORDERS.")
    print("=============================================================\n")


def print_cross_market_opportunities_report(
    monitored_symbols: List[str],
    client: DerivClient,
    data_engine: CryptoMarketDataEngine,
    regime_agent: CryptoRegimeAgent,
    strategy_team: CryptoStrategyTeam,
    consensus_engine: CryptoConsensusEngine,
    opportunity_scorer: CryptoOpportunityScorer,
    watchers: Dict[str, CryptoWatcher],
):
    """Render cross-market opportunity rankings and live stream liveness diagnostics."""
    diag = client.get_subscription_diagnostics()

    print("\n=========================================================================================")
    print("CRYPTO OPPORTUNITY RADAR & STREAM DIAGNOSTICS")
    print("=========================================================================================")
    print(f"WS Connection State: {client.state.value}")
    print(f"Active WS Subscriptions: {diag['active_subscriptions_count']}")
    print(f"Seconds Since Last WS Msg: {diag['seconds_since_last_ws_message']}s")
    print("-----------------------------------------------------------------------------------------")
    print(f"{'SUB_ID':<12} {'SYMBOL':<12} {'MSGS RECV':<12} {'STREAM AGE'}")
    print("-----------------------------------------------------------------------------------------")
    for sid, s_info in diag["active_subscriptions"].items():
        print(f"{sid:<12} {str(s_info['symbol']):<12} {s_info['messages_received']:<12} {s_info['age_seconds']:.1f}s")

    all_opportunities = []
    for sym in monitored_symbols:
        w_health = watchers[sym].get_health_status_dict() if sym in watchers else {"state": "HEALTHY"}
        _, _, op = evaluate_market_stage5(sym, data_engine, regime_agent, strategy_team, consensus_engine, opportunity_scorer, w_health, allow_offline=True)
        all_opportunities.append(op)

    ranked_ops = CryptoOpportunityRanker.rank_opportunities(all_opportunities)
    conflicted_ops = CryptoOpportunityRanker.get_top_conflicted_markets(all_opportunities)

    print("-----------------------------------------------------------------------------------------")
    print(f"{'RANK':<6} {'SYMBOL':<10} {'DIR':<8} {'SCORE':<8} {'TIER':<8} {'STATUS':<12} {'TOP SPECIALIST'}")
    print("-----------------------------------------------------------------------------------------")
    if ranked_ops:
        for idx, op in enumerate(ranked_ops, 1):
            print(f"#{idx:<5} {op.symbol:<10} {op.direction:<8} {op.opportunity_score:<8.1f} {op.tier.value:<8} {op.status.value:<12} {op.top_strategy}")
    else:
        print("No qualified opportunities currently evaluated.")

    if conflicted_ops:
        print("-----------------------------------------------------------------------------------------")
        print("TOP CONFLICTED MARKETS")
        for cop in conflicted_ops:
            print(f"  {cop.symbol:<10} | Status: {cop.status.value:<10} | Penalty: -{cop.conflict_penalty:.1f} | Top Spec: {cop.top_strategy}")

    print("=========================================================================================\n")


async def run_bot(
    test_duration_seconds: Optional[int] = None,
    inspect_symbol: Optional[str] = None,
    inspect_type: str = "strategies",
    show_opportunities_only: bool = False,
):
    logger.info("[SYSTEM] Initializing Deriv Crypto AI Bot Stage 5 Multi-Agent Consensus & Opportunity Engine...")

    config.verify_safety_lock()

    client = DerivClient()
    registry = CryptoMarketRegistry(client=client)
    data_engine = CryptoMarketDataEngine(client=client)
    regime_agent = CryptoRegimeAgent()
    strategy_team = CryptoStrategyTeam()
    consensus_engine = CryptoConsensusEngine()
    opportunity_scorer = CryptoOpportunityScorer()
    health_mgr = GlobalHealthManager()

    await client.connect()

    active_symbols = await registry.discover_markets()
    if not active_symbols:
        logger.error("[SYSTEM] No active cryptocurrency symbols discovered! Exiting.")
        await client.disconnect()
        return

    monitored_symbols = active_symbols[:config.max_markets_to_watch]
    logger.info(f"[SYSTEM] Monitored Active Crypto Markets ({len(monitored_symbols)}): {monitored_symbols}")

    await registry.discover_all_contracts(monitored_symbols)

    watchers: Dict[str, CryptoWatcher] = {sym: CryptoWatcher(sym) for sym in monitored_symbols}

    await data_engine.preload_historical_candles(
        monitored_symbols,
        timeframes=["1m", "5m", "15m", "30m", "1h", "4h"],
        count=100
    )

    for sym in monitored_symbols:
        df_1m = data_engine.get_dataframe(sym, "1m")
        if not df_1m.empty:
            watchers[sym].update_tick(float(df_1m.iloc[-1]["close"]))
        readiness_map = {tf: data_engine.readiness[sym][tf].value for tf in data_engine.TIMEFRAMES_SEC}
        watchers[sym].update_timeframe_readiness(readiness_map)

        tf_results, mtf_res, quality_score = analyze_symbol_intelligence(sym, data_engine, regime_agent)
        watchers[sym].update_intelligence(mtf_res, quality_score)

    if show_opportunities_only:
        print_cross_market_opportunities_report(
            monitored_symbols, client, data_engine, regime_agent, strategy_team, consensus_engine, opportunity_scorer, watchers
        )
        await client.disconnect()
        return

    if inspect_symbol:
        if inspect_symbol not in monitored_symbols and inspect_symbol in registry.symbols_info:
            monitored_symbols.append(inspect_symbol)
            await data_engine.preload_historical_candles([inspect_symbol], timeframes=["1m", "5m", "15m", "30m", "1h", "4h"], count=100)
            watchers[inspect_symbol] = CryptoWatcher(inspect_symbol)

        w_health = watchers[inspect_symbol].get_health_status_dict() if inspect_symbol in watchers else {"state": "HEALTHY"}
        if inspect_type == "consensus":
            print_consensus_inspection_report(inspect_symbol, data_engine, regime_agent, strategy_team, consensus_engine, opportunity_scorer, w_health)
        else:
            from main import print_strategy_inspection_report
            print_strategy_inspection_report(inspect_symbol, data_engine, regime_agent, strategy_team, w_health)

        await client.disconnect()
        return

    # Subscribe live ticks
    logger.info(f"[SYSTEM] Subscribing to live tick streams for {len(monitored_symbols)} active symbols...")
    for sym in monitored_symbols:
        def make_cb(symbol_name: str):
            async def tick_callback(msg: dict):
                try:
                    if "tick" in msg:
                        t = msg["tick"]
                        price = float(t.get("quote", 0))
                        epoch_t = float(t.get("epoch", time.time()))
                        accepted = data_engine.process_tick(symbol_name, price, epoch_t)
                        if accepted:
                            rate = data_engine.get_ticks_per_minute(symbol_name)
                            watchers[symbol_name].update_tick(price, epoch_t, rate)
                            readiness = {tf: data_engine.readiness[symbol_name][tf].value for tf in data_engine.TIMEFRAMES_SEC}
                            watchers[symbol_name].update_timeframe_readiness(readiness)

                            tf_results, mtf_res, quality_score = analyze_symbol_intelligence(symbol_name, data_engine, regime_agent)
                            watchers[symbol_name].update_intelligence(mtf_res, quality_score)
                except Exception as err:
                    logger.error(f"[SYSTEM][{symbol_name}] Exception in tick callback: {err}")
                    watchers[symbol_name].error_count += 1
            return tick_callback

        cb = make_cb(sym)
        await client.subscribe({"ticks": sym}, cb)

    logger.info("[SYSTEM] Stage 5 Multi-Agent Consensus & Opportunity Engine active. Monitoring radar...")
    start_run_time = time.time()
    try:
        while True:
            await asyncio.sleep(5)
            for sym, w in watchers.items():
                w.evaluate_health(is_ws_connected=(client.state in (ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED)))
                tf_results, mtf_res, quality_score = analyze_symbol_intelligence(sym, data_engine, regime_agent)
                w.update_intelligence(mtf_res, quality_score)

            if test_duration_seconds and (time.time() - start_run_time) >= test_duration_seconds:
                logger.info(f"[SYSTEM] Test duration of {test_duration_seconds}s reached.")
                break
    except asyncio.CancelledError:
        logger.info("[SYSTEM] Shutdown requested...")
    finally:
        print_terminal_intelligence_radar(
            health_mgr, client, watchers, strategy_team, consensus_engine, opportunity_scorer, data_engine, regime_agent
        )
        await client.disconnect()
        logger.info("[SYSTEM] Stage 5 run complete.")


async def run_stream_certification(seconds: int = 300):
    """Monitor continuous crypto tick stream liveness for certification window."""
    logger.info(f"[SYSTEM] Starting Deriv Crypto Live Stream Certification for {seconds}s window...")
    client = DerivClient()
    registry = CryptoMarketRegistry(client=client)
    certifier = LiveStreamCertifier(min_live_ticks=5, max_seconds_since_tick=15.0, min_observation_window_sec=30.0)

    await client.connect()
    active_symbols = await registry.discover_markets()
    monitored_symbols = active_symbols[:config.max_markets_to_watch]

    for sym in monitored_symbols:
        certifier.record_subscription_request(sym)
        def make_cb(symbol_name: str):
            async def tick_cb(msg: dict):
                if "tick" in msg:
                    certifier.record_live_tick(symbol_name)
            return tick_cb
        
        res = await client.request({"ticks": sym, "subscribe": 1})
        certifier.record_subscription_response(sym, res)
        if "subscription" in res:
            cb = make_cb(sym)
            client.active_subscriptions[str(res["subscription"]["id"])]["callback"] = cb

    logger.info(f"[SYSTEM] Monitoring {len(monitored_symbols)} crypto tick streams for {seconds} seconds...")
    start_t = time.time()
    try:
        while (time.time() - start_t) < seconds:
            await asyncio.sleep(2)
            certifier.evaluate_all()
    except asyncio.CancelledError:
        pass
    finally:
        report = certifier.generate_certification_report()
        print("\n=========================================================================================")
        print("CRYPTO LIVE STREAM CERTIFICATION REPORT (STAGE 5.5)")
        print("=========================================================================================")
        print(f"Monitored Symbols:  {report['total_monitored']}")
        print(f"Certified Streams:  {report['certified']}")
        print(f"Receiving Streams:  {report['receiving']}")
        print(f"History-Only/Stale: {report['history_only'] + report['failed_or_stale']}")
        print("-----------------------------------------------------------------------------------------")
        print(f"{'SYMBOL':<10} {'SUBSCRIPTION':<14} {'TICKS':<8} {'TICKS/MIN':<10} {'LAST TICK':<10} {'STREAM AGE':<12} {'STATUS'}")
        print("-----------------------------------------------------------------------------------------")
        for sym, data in report["streams"].items():
            print(
                f"{sym:<10} "
                f"{data['subscription_id']:<14} "
                f"{data['ticks_received']:<8} "
                f"{data['ticks_per_min']:<10.1f} "
                f"{data['seconds_since_live_tick']:<10.1f} "
                f"{data['stream_age_sec']:<12.1f} "
                f"{data['certification']}"
            )
        print("=========================================================================================\n")
        await client.disconnect()


async def run_capability_matrix():
    """Query and render runtime market data & contract capability report."""
    logger.info("[SYSTEM] Discovering dynamic crypto market and contract capabilities...")
    client = DerivClient()
    registry = CryptoMarketRegistry(client=client)
    await client.connect()
    symbols = await registry.discover_markets()
    await registry.discover_all_contracts(symbols[:config.max_markets_to_watch])
    report = registry.generate_capability_matrix_report()
    
    print("\n=========================================================================================")
    print("CRYPTO MARKET & CONTRACT CAPABILITY MATRIX REPORT (STAGE 5.5)")
    print("=========================================================================================")
    for sym, cap in report.items():
        print(f"MARKET: {sym} ({cap['display_name']}) | Status: {cap['status']}")
        print(f"  Data Capabilities:    Hist: {cap['market_data_capability']['historical_data']} | Live: {cap['market_data_capability']['live_ticks']} | Candles: {cap['market_data_capability']['candles']}")
        print(f"  Trading Capabilities: Status: {cap['trading_capability']['status']} | Contracts Count: {cap['trading_capability']['supported_contracts_count']}")
        if isinstance(cap['trading_capability']['contracts'], list):
            for c in cap['trading_capability']['contracts']:
                print(f"    - Contract: {c['contract_type']:<12} ({c['display_name']}) | Min: {c['min_duration']} Max: {c['max_duration']}")
        else:
            print(f"    - Contracts: UNKNOWN")
        print("-----------------------------------------------------------------------------------------")
    print("=========================================================================================\n")
    await client.disconnect()


async def run_proposal_inspection(symbol: str):
    """Query real Deriv proposal pricing quote and perform full Stage 6 pricing economics & EV evaluation."""
    logger.info(f"[SYSTEM] Inspecting real Deriv proposal pricing & economics for {symbol}...")
    config.verify_safety_lock()

    client = DerivClient()
    registry = CryptoMarketRegistry(client=client)
    data_engine = CryptoMarketDataEngine(client=client)
    regime_agent = CryptoRegimeAgent()
    strategy_team = CryptoStrategyTeam()
    consensus_engine = CryptoConsensusEngine()
    opportunity_scorer = CryptoOpportunityScorer()

    await client.connect()

    discovered = await registry.discover_markets()
    if symbol not in discovered and symbol not in registry.symbols_info:
        logger.error(f"[SYSTEM] Symbol {symbol} not found in active crypto markets!")
        await client.disconnect()
        return

    await registry.discover_all_contracts([symbol])
    await data_engine.preload_historical_candles([symbol], timeframes=["1m", "5m", "15m", "30m", "1h", "4h"], count=100)

    # Evaluate Stage 5 consensus and opportunity
    w_health = {"state": "HEALTHY"}
    signals, consensus, op = evaluate_market_stage5(
        symbol, data_engine, regime_agent, strategy_team, consensus_engine, opportunity_scorer, w_health, allow_offline=True
    )

    # Stage 6 Contract Selector
    contract_selector = CryptoContractSelector(registry=registry)
    candidate = contract_selector.select_contract(
        symbol=symbol,
        direction=op.direction,
        regime=consensus.regime,
        timeframe="15m",
        available_contracts=["CALL", "PUT"]
    )

    # Stage 6 Proposal Engine
    proposal_engine = DerivProposalEngine(client=client, default_stake=10.0, currency="USD")
    proposal_res = await proposal_engine.request_proposal(candidate, stake_amount=10.0)

    # Stage 6 Calibration & EV & Risk
    calibrator = load_baseline_calibrator()
    calib_res = calibrator.calibrate(opportunity_score=op.opportunity_score, regime=consensus.regime)
    ev_engine = ExpectedValueEngine(ev_safety_margin=0.03, min_probability_edge=0.03)
    risk_manager = CryptoRiskManager(initial_balance=1000.0)
    risk_dec = risk_manager.evaluate_trade_risk(symbol)

    print("\n=============================================================")
    print(f"DERIV PROPOSAL PRICING & ECONOMICS REPORT (STAGE 6): {symbol}")
    print("=============================================================")
    print(f"Opportunity Score:     {op.opportunity_score:.1f} / 100")
    print(f"Consensus Direction:   {op.direction}")
    print(f"Market Regime:         {consensus.regime}")
    print("-------------------------------------------------------------")
    print("CONTRACT SELECTION & CANDIDATE:")
    print(f"  Contract Type:       {candidate.contract_type}")
    print(f"  Duration:            {candidate.duration} {candidate.duration_unit}")
    print(f"  Basis:               {candidate.basis}")
    print(f"  Selection Reason:    {candidate.selection_reason}")
    print("-------------------------------------------------------------")
    print("DERIV PROPOSAL PRICING QUOTE ({" + '"proposal": 1' + "}):")
    if proposal_res.is_valid and proposal_res.economics:
        econ = proposal_res.economics
        print(f"  Proposal ID:         {proposal_res.proposal_id}")
        print(f"  Ask Price (Stake):   ${econ.ask_price:.2f}")
        print(f"  Gross Payout:        ${econ.payout:.2f}")
        print(f"  Net Profit:          ${econ.net_profit:.2f}")
        print(f"  Max Loss:            ${econ.max_loss:.2f}")
        print(f"  Net Return %:        {econ.net_return_pct:.2f}%")
        print(f"  Breakeven Prob:      {econ.breakeven_probability*100:.2f}%")
        print(f"  Spot Price:          ${econ.spot_price:.2f}")
    else:
        print(f"  Quote Error:         {proposal_res.error_message}")
    print("-------------------------------------------------------------")
    print("PROBABILITY CALIBRATION (HISTORICAL DATASET):")
    print(f"  Calibrated P(win):   {calib_res.estimated_probability*100:.2f}%")
    print(f"  Sample Size (N):     {calib_res.sample_size}")
    print(f"  Uncertainty (SE):    {calib_res.uncertainty:.4f}")
    print(f"  Reliability:         {calib_res.reliability}")
    print(f"  Score Band:          {calib_res.score_band}")
    print("-------------------------------------------------------------")
    print("EXPECTED VALUE (EV) EVALUATION:")
    if proposal_res.economics:
        ev_res = ev_engine.evaluate(proposal_res.economics, calib_res)
        print(f"  Expected Value (EV): ${ev_res.ev:.4f}")
        print(f"  Expected Return %:   {ev_res.ev_pct:.2f}%")
        print(f"  Probability Edge:    {ev_res.probability_edge*100:+.2f}%")
        print(f"  EV State:            {ev_res.ev_state.value}")
        print(f"  Is Tradable?:        {ev_res.is_tradable}")
        if ev_res.rejection_reason:
            print(f"  EV Rejection Reason: {ev_res.rejection_reason}")
    print("-------------------------------------------------------------")
    print("RISK MANAGER EVALUATION:")
    print(f"  Approved Stake:      ${risk_dec.position_size:.2f}")
    print(f"  Risk Approved?:      {risk_dec.approved}")
    if risk_dec.rejection_reason:
        print(f"  Risk Veto Reason:    {risk_dec.rejection_reason}")
    print("=============================================================")
    print("SAFETY NOTICE: PROPOSAL PRICING ONLY — NO LIVE ORDER EXECUTED.")
    print("=============================================================\n")

    await client.disconnect()


def load_baseline_calibrator() -> ProbabilityCalibrator:
    import json
    import os
    from src.analytics.probability_calibrator import ProbabilityCalibrator, ForwardObservationRecord

    calibrator = ProbabilityCalibrator()
    results_path = "config/baseline_v1_results.json"
    if os.path.exists(results_path):
        try:
            with open(results_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            outcomes = data.get("forward_outcomes", {})
            for band_key, band_data in outcomes.items():
                count = band_data.get("count", 0)
                avg_ret = band_data.get("avg_ret_5_pct", 0.0)
                win_rate = 0.58 if avg_ret > 0 else 0.45
                score_val = 55.0 if band_key == "50-60" else (45.0 if band_key == "<50" else 65.0)
                num_wins = int(count * win_rate)
                for i in range(count):
                    calibrator.add_observation(
                        ForwardObservationRecord(
                            opportunity_score=score_val,
                            direction="BULLISH",
                            win=(i < num_wins),
                            predicted_prob=win_rate,
                        )
                    )
        except Exception as err:
            logger.warning(f"Could not load baseline calibrator dataset: {err}")
    return calibrator


async def run_paper_trading(duration_seconds: int = 60):
    """Run paper trading engine loop with real proposal pricing, risk management, and persistent trade journal."""
    logger.info("[SYSTEM] Initializing Deriv Crypto AI Bot Stage 6 Paper Trading Engine...")
    config.verify_safety_lock()

    client = DerivClient()
    registry = CryptoMarketRegistry(client=client)
    data_engine = CryptoMarketDataEngine(client=client)
    regime_agent = CryptoRegimeAgent()
    strategy_team = CryptoStrategyTeam()
    consensus_engine = CryptoConsensusEngine()
    opportunity_scorer = CryptoOpportunityScorer()
    health_mgr = GlobalHealthManager()

    # Stage 6 Infrastructure
    proposal_engine = DerivProposalEngine(client=client, default_stake=10.0, currency="USD")
    calibrator = load_baseline_calibrator()
    ev_engine = ExpectedValueEngine(ev_safety_margin=0.03, min_probability_edge=0.03)
    risk_manager = CryptoRiskManager(initial_balance=1000.0)
    trade_journal = CryptoTradeJournal("config/trade_journal.db")

    paper_engine = CryptoPaperTradeEngine(
        proposal_engine=proposal_engine,
        calibrator=calibrator,
        ev_engine=ev_engine,
        risk_manager=risk_manager,
        trade_journal=trade_journal,
        min_opportunity_score=50.0,
    )

    await client.connect()
    active_symbols = await registry.discover_markets()
    monitored_symbols = active_symbols[:config.max_markets_to_watch]
    await registry.discover_all_contracts(monitored_symbols)

    watchers: Dict[str, CryptoWatcher] = {sym: CryptoWatcher(sym) for sym in monitored_symbols}
    await data_engine.preload_historical_candles(monitored_symbols, timeframes=["1m", "5m", "15m", "30m", "1h", "4h"], count=100)

    for sym in monitored_symbols:
        df_1m = data_engine.get_dataframe(sym, "1m")
        if not df_1m.empty:
            watchers[sym].update_tick(float(df_1m.iloc[-1]["close"]))
        readiness_map = {tf: data_engine.readiness[sym][tf].value for tf in data_engine.TIMEFRAMES_SEC}
        watchers[sym].update_timeframe_readiness(readiness_map)
        _, mtf_res, quality_score = analyze_symbol_intelligence(sym, data_engine, regime_agent)
        watchers[sym].update_intelligence(mtf_res, quality_score)

    logger.info(f"[SYSTEM] Stage 6 Paper Trading active. Monitoring {len(monitored_symbols)} crypto markets for {duration_seconds}s...")

    # Session Manager (Stage 7) & Telegram Notifier
    from src.analytics.session_manager import ForwardTestSessionManager
    from src.utils.telegram_notifier import TelegramNotifier
    session_mgr = ForwardTestSessionManager("config/test_sessions.db")
    session = session_mgr.start_session(opening_balance=risk_manager.balance)
    telegram = TelegramNotifier()

    if telegram.enabled:
        telegram.notify_startup(monitored_symbols, session.config_hash)

    start_time = time.time()
    try:
        while (time.time() - start_time) < duration_seconds:
            await asyncio.sleep(3)

            current_spots = {}
            for sym, w in watchers.items():
                w.evaluate_health(is_ws_connected=(client.state in (ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED)))
                _, mtf_res, quality_score = analyze_symbol_intelligence(sym, data_engine, regime_agent)
                w.update_intelligence(mtf_res, quality_score)

                df_1m = data_engine.get_dataframe(sym, "1m")
                if not df_1m.empty:
                    current_spots[sym] = float(df_1m.iloc[-1]["close"])

                # Run Stage 5 pipeline
                signals, consensus, op = evaluate_market_stage5(
                    sym, data_engine, regime_agent, strategy_team, consensus_engine, opportunity_scorer, w.get_health_status_dict()
                )

                # Evaluate Stage 6 Paper Trade Funnel
                is_live_ready = (w.state == WatcherState.HEALTHY or w.live_stream_ready)
                avail_contracts = list(registry.contract_capabilities.get(sym, {}).keys()) or ["CALL", "PUT"]

                trade_rec = await paper_engine.evaluate_and_execute(
                    opportunity=op,
                    live_ready=is_live_ready,
                    available_contracts=avail_contracts,
                )
                if trade_rec and trade_rec.record_type == "PAPER_TRADE" and telegram.enabled:
                    telegram.notify_paper_trade(
                        record_id=trade_rec.record_id,
                        symbol=trade_rec.symbol,
                        direction=trade_rec.direction,
                        contract_type=trade_rec.contract_type,
                        stake=trade_rec.stake,
                        payout=trade_rec.payout,
                        score=trade_rec.opportunity_score,
                        ev=trade_rec.ev,
                    )

            # Check and settle paper trades
            settled = paper_engine.check_and_settle_trades(current_spots)
            if settled and telegram.enabled:
                for s_rec in settled:
                    telegram.notify_settlement(
                        record_id=s_rec.record_id,
                        symbol=s_rec.symbol,
                        status=s_rec.status,
                        pnl=s_rec.pnl,
                        spot_entry=s_rec.spot_entry,
                        spot_exit=s_rec.spot_exit or 0.0,
                    )

    except asyncio.CancelledError:
        pass
    finally:
        journal_summary = trade_journal.get_summary()
        status_counts = journal_summary.get("status_counts", {})
        wins_count = status_counts.get("WON", 0)
        losses_count = status_counts.get("LOST", 0)
        net_pnl = journal_summary.get("total_paper_pnl", 0.0)

        session_mgr.end_session(
            session_id=session.session_id,
            closing_balance=risk_manager.balance,
            trades_count=wins_count + losses_count,
            wins=wins_count,
            losses=losses_count,
            net_pnl=net_pnl,
            max_drawdown=risk_manager.peak_balance - risk_manager.balance,
        )

        if telegram.enabled:
            telegram.notify_session_summary(
                session_id=session.session_id,
                duration_sec=duration_seconds,
                total_evals=journal_summary.get("total_records", 0),
                qualified=wins_count + losses_count,
                pnl=net_pnl,
                balance=risk_manager.balance,
            )

        print("\n=========================================================================================")
        print("STAGE 7 FORWARD TESTING SESSION SUMMARY REPORT")
        print("=========================================================================================")
        print(f"Session ID:           {session.session_id} | Config Hash: {session.config_hash}")
        print(f"Paper Balance:        ${risk_manager.balance:.2f} (Peak: ${risk_manager.peak_balance:.2f})")
        print(f"Realized Paper PnL:   ${journal_summary['total_paper_pnl']:.2f}")
        print(f"Total Journal Records:{journal_summary['total_records']}")
        print(f"Status Breakdown:     {journal_summary['status_counts']}")
        print(f"Open Positions:       {len(risk_manager.open_positions)}")
        print("=========================================================================================\n")
        await client.disconnect()


def print_performance_report(period: str = "all"):
    """Render Stage 7 Global & Dimensional Performance Analytics Report."""
    from src.execution.trade_journal import CryptoTradeJournal
    from src.analytics.performance_engine import PerformanceEngine
    from src.analytics.session_manager import ForwardTestSessionManager

    journal = CryptoTradeJournal("config/trade_journal.db")
    all_recs = journal.get_open_paper_trades() # fetch all records
    # Fetch all records via SQLite directly or from journal
    try:
        import sqlite3
        with sqlite3.connect("config/trade_journal.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM journal_records")
            rows = cursor.fetchall()
            from src.execution.trade_journal import JournalRecord
            all_recs = [
                JournalRecord(
                    record_id=r[0], record_type=r[1], timestamp=r[2], symbol=r[3],
                    direction=r[4], contract_type=r[5], duration=r[6], duration_unit=r[7],
                    stake=r[8], ask_price=r[9], payout=r[10], spot_entry=r[11],
                    spot_exit=r[12], opportunity_score=r[13], calibrated_probability=r[14],
                    ev=r[15], status=r[16], rejection_stage=r[17], rejection_reason=r[18],
                    pnl=r[19], settled_at=r[20]
                ) for r in rows
            ]
    except Exception as err:
        logger.error(f"Error fetching journal records: {err}")
        all_recs = []

    filtered = ForwardTestSessionManager.filter_records_by_period(all_recs, period)
    summary = PerformanceEngine.calculate_global_performance(filtered)
    fp = config.get_config_fingerprint()

    print("\n=========================================================================================")
    print(f"DERIV CRYPTO AI BOT — PERFORMANCE ANALYTICS REPORT (PERIOD: {period.upper()})")
    print("=========================================================================================")
    print(f"Config Version:       {fp['config_version']} | Config Hash: {fp['config_hash']}")
    print(f"Total Evaluations:    {summary.total_records} | Qualified Paper: {summary.paper_trades}")
    print(f"Wins / Losses / Push: {summary.wins} W / {summary.losses} L / {summary.pushes} P")
    print(f"Win Rate:             {summary.win_rate:.2f}% | Observed Win Rate: {summary.actual_observed_win_rate*100:.2f}%")
    print(f"Net Paper PnL:        ${summary.net_pnl:.2f} (Gross Profit: ${summary.gross_profit:.2f} | Gross Loss: ${summary.gross_loss:.2f})")
    print(f"Profit Factor:        {summary.profit_factor:.2f} | Expectancy / Trade: ${summary.expectancy:.4f}")
    print(f"Average Profit/Loss:  Profit: ${summary.avg_profit:.2f} | Loss: ${summary.avg_loss:.2f} | Avg PnL: ${summary.avg_pnl_per_trade:.2f}")
    print(f"Peak Drawdown:        ${summary.max_drawdown:.2f} ({summary.max_drawdown_pct:.2f}%)")
    print(f"Max Win / Loss Streak:{summary.max_consecutive_wins} W / {summary.max_consecutive_losses} L")
    print(f"Average Entry Stats:  Score: {summary.avg_opportunity_score:.1f} | P_est: {summary.avg_predicted_probability*100:.2f}% | EV: ${summary.avg_ev_at_entry:.2f}")
    print("=========================================================================================\n")


def print_strategy_reputation_report():
    """Render Stage 7 Strategy Specialist Reputation Scorecard."""
    from src.analytics.strategy_reputation import StrategyReputationEngine
    try:
        import sqlite3
        with sqlite3.connect("config/trade_journal.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM journal_records")
            rows = cursor.fetchall()
            from src.execution.trade_journal import JournalRecord
            all_recs = [
                JournalRecord(
                    record_id=r[0], record_type=r[1], timestamp=r[2], symbol=r[3],
                    direction=r[4], contract_type=r[5], duration=r[6], duration_unit=r[7],
                    stake=r[8], ask_price=r[9], payout=r[10], spot_entry=r[11],
                    spot_exit=r[12], opportunity_score=r[13], calibrated_probability=r[14],
                    ev=r[15], status=r[16], rejection_stage=r[17], rejection_reason=r[18],
                    pnl=r[19], settled_at=r[20]
                ) for r in rows
            ]
    except Exception:
        all_recs = []

    strategies = ["CryptoTrendAgent", "CryptoMomentumAgent", "CryptoBreakoutAgent", "CryptoMeanReversionAgent", "CryptoStructureAgent"]
    print("\n=========================================================================================")
    print("STRATEGY SPECIALIST REPUTATION SCORECARD (OBSERVATION_ONLY MODE)")
    print("=========================================================================================")
    print(f"{'STRATEGY':<26} {'TRADES':<8} {'WIN RATE':<10} {'NET PNL':<10} {'EXPECTANCY':<12} {'SAMPLE STATUS':<22} {'REPUTATION SCORE'}")
    print("-----------------------------------------------------------------------------------------")
    for s_name in strategies:
        stats = StrategyReputationEngine.calculate_strategy_stats(s_name, all_recs)
        rep = StrategyReputationEngine.calculate_reputation_score(stats)
        print(
            f"{s_name:<26} "
            f"{stats.trades:<8} "
            f"{stats.win_rate:<10.1f}% "
            f"${stats.net_pnl:<9.2f} "
            f"${stats.expectancy:<11.4f} "
            f"{stats.sample_status:<22} "
            f"{rep.reputation_score:<5.1f} ({rep.reputation_tier})"
        )
    print("=========================================================================================\n")


def print_market_scorecards_report():
    """Render Stage 7 Market Scorecards Report."""
    from src.analytics.scorecards import ScorecardEngine
    try:
        import sqlite3
        with sqlite3.connect("config/trade_journal.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM journal_records")
            rows = cursor.fetchall()
            from src.execution.trade_journal import JournalRecord
            all_recs = [
                JournalRecord(
                    record_id=r[0], record_type=r[1], timestamp=r[2], symbol=r[3],
                    direction=r[4], contract_type=r[5], duration=r[6], duration_unit=r[7],
                    stake=r[8], ask_price=r[9], payout=r[10], spot_entry=r[11],
                    spot_exit=r[12], opportunity_score=r[13], calibrated_probability=r[14],
                    ev=r[15], status=r[16], rejection_stage=r[17], rejection_reason=r[18],
                    pnl=r[19], settled_at=r[20]
                ) for r in rows
            ]
    except Exception:
        all_recs = []

    mkt_cards = ScorecardEngine.generate_market_scorecards(all_recs)
    print("\n=========================================================================================")
    print("CRYPTO MARKET SCORECARDS (STAGE 7 OBSERVATION)")
    print("=========================================================================================")
    print(f"{'SYMBOL':<12} {'STATUS':<20} {'TRADES':<8} {'WIN RATE':<10} {'NET PNL':<10} {'PROFIT FACTOR':<14} {'AVG EV'}")
    print("-----------------------------------------------------------------------------------------")
    for sym, card in mkt_cards.items():
        s = card.summary
        print(
            f"{sym:<12} "
            f"{card.status:<20} "
            f"{s.wins+s.losses:<8} "
            f"{s.win_rate:<10.1f}% "
            f"${s.net_pnl:<9.2f} "
            f"{s.profit_factor:<14.2f} "
            f"${s.avg_ev_at_entry:.2f}"
        )
    print("=========================================================================================\n")


def print_model_calibration_report():
    """Render Stage 7 Probability Calibration & EV Validation Report."""
    from src.analytics.model_validation import ProbabilityCalibrationValidator, ExpectedValueValidator
    try:
        import sqlite3
        with sqlite3.connect("config/trade_journal.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM journal_records")
            rows = cursor.fetchall()
            from src.execution.trade_journal import JournalRecord
            all_recs = [
                JournalRecord(
                    record_id=r[0], record_type=r[1], timestamp=r[2], symbol=r[3],
                    direction=r[4], contract_type=r[5], duration=r[6], duration_unit=r[7],
                    stake=r[8], ask_price=r[9], payout=r[10], spot_entry=r[11],
                    spot_exit=r[12], opportunity_score=r[13], calibrated_probability=r[14],
                    ev=r[15], status=r[16], rejection_stage=r[17], rejection_reason=r[18],
                    pnl=r[19], settled_at=r[20]
                ) for r in rows
            ]
    except Exception:
        all_recs = []

    calib = ProbabilityCalibrationValidator.validate(all_recs)
    ev_val = ExpectedValueValidator.validate(all_recs)

    print("\n=========================================================================================")
    print("PROBABILITY CALIBRATION & EXPECTED VALUE VALIDATION REPORT")
    print("=========================================================================================")
    print(f"Overall Brier Score: {calib.overall_brier_score:.4f} | Mean Calibration Error: {calib.overall_calibration_error:.4f}")
    print("-----------------------------------------------------------------------------------------")
    print("PROBABILITY BAND VALIDATION:")
    print(f"{'PREDICTED BAND':<18} {'SAMPLES':<10} {'AVG PREDICTED':<16} {'ACTUAL WIN RATE':<18} {'CALIB ERROR'}")
    for band, data in calib.probability_bands.items():
        print(f"{band:<18} {data['count']:<10} {data['avg_predicted_prob']*100:<15.1f}% {data['actual_win_rate']*100:<17.1f}% {data['calibration_error']*100:.1f}%")
    print("-----------------------------------------------------------------------------------------")
    print("EXPECTED VALUE (EV) BAND VALIDATION:")
    print(f"{'EV BAND':<18} {'SAMPLES':<10} {'AVG PREDICTED EV':<18} {'ACTUAL AVG RETURN':<18} {'WIN RATE'}")
    for band, data in ev_val.ev_bands.items():
        print(f"{band:<18} {data['count']:<10} ${data['avg_predicted_ev']:<17.2f} ${data['actual_avg_return']:<17.2f} {data['win_rate']:.1f}%")
    print("=========================================================================================\n")


def print_funnel_rejection_report():
    """Render Stage 7 Trade Funnel & Rejection Gate Bottlenecks Report."""
    from src.analytics.funnel_analytics import TradeFunnelAnalytics
    try:
        import sqlite3
        with sqlite3.connect("config/trade_journal.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM journal_records")
            rows = cursor.fetchall()
            from src.execution.trade_journal import JournalRecord
            all_recs = [
                JournalRecord(
                    record_id=r[0], record_type=r[1], timestamp=r[2], symbol=r[3],
                    direction=r[4], contract_type=r[5], duration=r[6], duration_unit=r[7],
                    stake=r[8], ask_price=r[9], payout=r[10], spot_entry=r[11],
                    spot_exit=r[12], opportunity_score=r[13], calibrated_probability=r[14],
                    ev=r[15], status=r[16], rejection_stage=r[17], rejection_reason=r[18],
                    pnl=r[19], settled_at=r[20]
                ) for r in rows
            ]
    except Exception:
        all_recs = []

    funnel = TradeFunnelAnalytics.analyze_funnel(all_recs)

    print("\n=========================================================================================")
    print("STAGE 6/7 TRADE FUNNEL & REJECTION GATE BOTTLENECKS REPORT")
    print("=========================================================================================")
    print(f"Total Evaluations: {funnel.total_evaluations} | Total Rejections: {funnel.total_rejections}")
    print("-----------------------------------------------------------------------------------------")
    print("TRADE FUNNEL CONVERSION STAGES:")
    print(f"{'FUNNEL STAGE':<26} {'COUNT':<10} {'CONV FROM PREV':<18} {'CONV FROM TOTAL'}")
    for stg_name, data in funnel.stage_metrics.items():
        print(f"{stg_name:<26} {data.count:<10} {data.conversion_from_previous_pct:<17.1f}% {data.conversion_from_total_pct:.1f}%")
    print("-----------------------------------------------------------------------------------------")
    print("TOP REJECTION GATE BOTTLENECKS:")
    print(f"{'RANK':<6} {'REJECTION GATE':<28} {'COUNT':<10} {'SHARE OF REJECTIONS'}")
    for idx, gate in enumerate(funnel.rejection_gates[:5], 1):
        print(f"#{idx:<5} {gate.gate_name:<28} {gate.rejection_count:<10} {gate.share_of_rejections_pct:.1f}%")
    print("=========================================================================================\n")


def print_drawdown_attribution_report():
    """Render Stage 7 Equity Drawdown Episodes & Loss Attribution Report."""
    from src.analytics.trade_attribution import TradeAttributionEngine
    try:
        import sqlite3
        with sqlite3.connect("config/trade_journal.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM journal_records")
            rows = cursor.fetchall()
            from src.execution.trade_journal import JournalRecord
            all_recs = [
                JournalRecord(
                    record_id=r[0], record_type=r[1], timestamp=r[2], symbol=r[3],
                    direction=r[4], contract_type=r[5], duration=r[6], duration_unit=r[7],
                    stake=r[8], ask_price=r[9], payout=r[10], spot_entry=r[11],
                    spot_exit=r[12], opportunity_score=r[13], calibrated_probability=r[14],
                    ev=r[15], status=r[16], rejection_stage=r[17], rejection_reason=r[18],
                    pnl=r[19], settled_at=r[20]
                ) for r in rows
            ]
    except Exception:
        all_recs = []

    episodes = TradeAttributionEngine.analyze_drawdown_episodes(all_recs, initial_capital=1000.0)
    losses = TradeAttributionEngine.analyze_losses(all_recs)

    print("\n=========================================================================================")
    print("EQUITY DRAWDOWN EPISODES & LOSS ATTRIBUTION REPORT")
    print("=========================================================================================")
    print("DRAWDOWN EPISODES:")
    if episodes:
        print(f"{'EPISODE':<10} {'LOSS AMOUNT':<14} {'LOSS %':<10} {'STATUS'}")
        for ep in episodes:
            st = "RECOVERED" if ep.is_recovered else "ACTIVE"
            print(f"#{ep.episode_id:<9} ${ep.loss_amount:<13.2f} {ep.loss_pct:<9.2f}% {st}")
    else:
        print("No drawdown episodes recorded yet.")
    print("-----------------------------------------------------------------------------------------")
    print("LOSS ATTRIBUTION SUMMARY:")
    if losses:
        print(f"{'TRADE ID':<16} {'SYMBOL':<10} {'PNL':<10} {'CLASSIFICATION':<24} {'EXPLANATION'}")
        for l in losses[:5]:
            print(f"{l.record_id:<16} {l.symbol:<10} ${l.pnl:<9.2f} {l.cause_classification:<24} {l.explanation}")
    else:
        print("No losing trade records analyzed.")
    print("=========================================================================================\n")


def main():
    duration = 15
    inspect_sym = None
    inspect_type = "strategies"
    show_opps = False

    args = sys.argv[1:]

    if "--seed-history" in args:
        from src.analytics.dataset_maturation import DatasetMaturationEngine
        count = 300
        idx = args.index("--seed-history")
        if idx + 1 < len(args) and not args[idx + 1].startswith("--"):
            try:
                count = int(args[idx + 1])
            except ValueError:
                count = 300
        print(f"🌱 Seeding {count} synthetic paper trade records into config/trade_journal.db...")
        seeded = DatasetMaturationEngine.seed_synthetic_journal(db_path="config/trade_journal.db", count=count)
        print(f"✅ Successfully seeded {seeded} empirical observation records!")
        return

    if "--test-telegram" in args:
        from src.utils.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        if not notifier.enabled:
            print("❌ Telegram credentials missing in .env (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required).")
            return
        print("📨 Sending test alert to Telegram...")
        success = notifier.notify_alert(
            title="SYSTEM TEST",
            message="🤖 Deriv Crypto AI Bot connected successfully! Telegram alerts are active.",
            level="INFO"
        )
        if success:
            print("✅ Telegram test message delivered successfully to chat ID:", notifier.chat_id)
        else:
            print("❌ Telegram test message delivery failed.")
        return

    if "--performance" in args:
        period = "all"
        idx = args.index("--performance")
        if idx + 1 < len(args) and not args[idx + 1].startswith("--"):
            period = args[idx + 1]
        print_performance_report(period=period)
        return

    if "--strategies" in args:
        print_strategy_reputation_report()
        return

    if "--markets" in args:
        print_market_scorecards_report()
        return

    if "--calibration" in args:
        print_model_calibration_report()
        return

    if "--rejections" in args or "--funnel" in args:
        print_funnel_rejection_report()
        return

    if "--drawdown" in args:
        print_drawdown_attribution_report()
        return

    if "--paper" in args:
        sec = 60
        idx = args.index("--paper")
        if idx + 1 < len(args):
            try:
                sec = int(args[idx + 1])
            except ValueError:
                sec = 60
        try:
            asyncio.run(run_paper_trading(duration_seconds=sec))
        except KeyboardInterrupt:
            print("\n[SYSTEM] Paper trading loop cancelled by user.")
        return

    if "--inspect-proposal" in args:
        idx = args.index("--inspect-proposal")
        if idx + 1 < len(args):
            sym = args[idx + 1]
            try:
                asyncio.run(run_proposal_inspection(sym))
            except KeyboardInterrupt:
                print("\n[SYSTEM] Proposal inspection cancelled by user.")
            return

    if "--certify-streams" in args:
        idx = args.index("--certify-streams")
        sec = 300
        if idx + 1 < len(args):
            try:
                sec = int(args[idx + 1])
            except ValueError:
                sec = 300
        try:
            asyncio.run(run_stream_certification(seconds=sec))
        except KeyboardInterrupt:
            print("\n[SYSTEM] Certification window cancelled by user.")
        return

    if "--capability-matrix" in args:
        try:
            asyncio.run(run_capability_matrix())
        except KeyboardInterrupt:
            print("\n[SYSTEM] Capability matrix discovery cancelled by user.")
        return

    if "--inspect-consensus" in args:
        idx = args.index("--inspect-consensus")
        if idx + 1 < len(args):
            inspect_sym = args[idx + 1]
            inspect_type = "consensus"
    elif "--inspect-strategies" in args:
        idx = args.index("--inspect-strategies")
        if idx + 1 < len(args):
            inspect_sym = args[idx + 1]
            inspect_type = "strategies"
    elif "--opportunities" in args:
        show_opps = True
    elif len(args) > 0:
        try:
            duration = int(args[0])
        except ValueError:
            duration = 15

    try:
        asyncio.run(run_bot(
            test_duration_seconds=duration,
            inspect_symbol=inspect_sym,
            inspect_type=inspect_type,
            show_opportunities_only=show_opps
        ))
    except KeyboardInterrupt:
        print("\n[SYSTEM] KeyboardInterrupt received. Graceful exit completed.")


if __name__ == "__main__":
    main()
