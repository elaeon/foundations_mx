import polars as pl
import networkx as nx
from pathlib import Path
import argparse
import json


def cmd_search(input_file: str, keyword: str, output: str, limit: int | None = None) -> None:
    kw = keyword.lower()
    mask = (
        pl.col("Rubro").str.to_lowercase().str.contains(kw, literal=True)
        | pl.col("Misión").str.to_lowercase().str.contains(kw, literal=True)
        | pl.col("Actividad").str.to_lowercase().str.contains(kw, literal=True)
    )
    refs = (
        pl.scan_csv(input_file)
        .filter(mask)
        .select("ref")
        .collect()["ref"]
        .to_list()
    )

    if not refs:
        print(f"No foundations matched keyword: {keyword}")
        return

    if limit:
        refs = refs[:limit]

    lazy_frames = []
    total = len(refs)
    for i, ref in enumerate(refs, 1):
        print(f"Reading Destino de donativos: {i}/{total}", end="\r", flush=True)
        try:
            df = (
                pl.read_excel(
                    ref,
                    sheet_name="Destino de donativos",
                    columns=["Rfc", "Razón social", "Folio", "Concepto", "Sector beneficiado",
                             "Monto", "Número de beneficiados", "Entidad federativa", "Municipio"],
                )
                .cast({"Monto": pl.Float64, "Número de beneficiados": pl.Int64})
                .with_columns(pl.lit(ref).alias("ref"))
                .lazy()
            )
            lazy_frames.append(df)
        except ValueError:
            continue
    print()

    if not lazy_frames:
        print(f"No 'Destino de donativos' data found for keyword: {keyword}")
        return

    pl.concat(lazy_frames).collect().write_csv(output)
    print(f"Wrote {output} ({len(lazy_frames)} foundations matched)")


def _build_graph(input_file: str, limit: int | None = None) -> nx.DiGraph:
    refs = pl.read_csv(input_file, columns=["ref"])["ref"].to_list()
    if limit:
        refs = refs[:limit]
    total = len(refs)

    best: dict[str, tuple[str, str]] = {}
    for i, ref in enumerate(refs, 1):
        print(f"Indexing RFC files: {i}/{total}", end="\r", flush=True)
        try:
            row = (
                pl.read_excel(ref, sheet_name="Carátula", columns=["Folio", "Rfc"])
                .sort("Folio")
                .tail(1)
            )
            rfc_val = row["Rfc"][0]
            folio_val = row["Folio"][0]
        except Exception:
            continue
        if rfc_val not in best or folio_val > best[rfc_val][0]:
            best[rfc_val] = (folio_val, ref)
    print()

    G = nx.DiGraph()
    unique = list(best.items())
    for i, (rfc_val, (_, ref_path)) in enumerate(unique, 1):
        print(f"Building graph edges: {i}/{len(unique)}", end="\r", flush=True)
        try:
            df = (
                pl.read_excel(
                    ref_path,
                    sheet_name="Donativos otorgados",
                    columns=["Rfc destinatario", "Monto efectivo", "Monto especie"],
                )
                .drop_nulls(subset=["Rfc destinatario"])
                .with_columns(
                    pl.col("Monto efectivo").cast(pl.Float64).fill_null(0.0),
                    pl.col("Monto especie").cast(pl.Float64).fill_null(0.0),
                )
            )
            for dest, efectivo, especie in (
                df.group_by("Rfc destinatario")
                .agg(pl.col("Monto efectivo").sum(), pl.col("Monto especie").sum())
                .iter_rows()
            ):
                G.add_edge(rfc_val, dest, monto_efectivo=efectivo, monto_especie=especie)
        except ValueError:
            continue
    print()

    return G


def _shortest_cycles_distinct_prev(subG: nx.DiGraph, rfc: str, max_cycles: int | None):
    count = 0
    for prev in subG.predecessors(rfc):
        try:
            path = nx.shortest_path(subG, rfc, prev)
        except nx.NetworkXNoPath:
            continue
        yield path
        count += 1
        if max_cycles and count >= max_cycles:
            return


def _shortest_cycles_through(subG: nx.DiGraph, rfc: str, max_cycles: int | None):
    min_dist = None
    for succ in subG.successors(rfc):
        try:
            d = nx.shortest_path_length(subG, succ, rfc)
            if min_dist is None or d < min_dist:
                min_dist = d
        except nx.NetworkXNoPath:
            continue
    if min_dist is None:
        return
    count = 0
    for succ in subG.successors(rfc):
        for path in nx.all_simple_paths(subG, succ, rfc, cutoff=min_dist):
            if len(path) - 1 == min_dist:
                yield [rfc] + path[:-1]
                count += 1
                if max_cycles and count >= max_cycles:
                    return


def _cycles_through(subG: nx.DiGraph, rfc: str, max_cycles: int | None, max_depth: int | None) -> list[list[str]]:
    count = 0
    for succ in subG.successors(rfc):
        for path in nx.all_simple_paths(subG, succ, rfc, cutoff=max_depth):
            yield [rfc] + path[:-1]
            count += 1
            if max_cycles and count >= max_cycles:
                return


def _format_cycle(cycle: list[str], start: str, G: nx.DiGraph | None = None) -> str:
    idx = cycle.index(start)
    rotated = cycle[idx:] + cycle[:idx]
    nodes = rotated + [rotated[0]]
    if G is None:
        return " -> ".join(nodes)
    parts = []
    for i in range(len(nodes) - 1):
        src, dst = nodes[i], nodes[i + 1]
        data = G[src][dst] if G.has_edge(src, dst) else {}
        efectivo = data.get("monto_efectivo", 0)
        especie = data.get("monto_especie", 0)
        parts.append(f"{src} -[ef:{efectivo:,.0f} esp:{especie:,.0f}]->")
    parts.append(nodes[-1])
    return " ".join(parts)


def _print_cycles(found: list[str]) -> None:
    width = len(str(len(found)))
    print(f"\n{'─' * 60}")
    print(f"  {len(found)} cycle(s) found")
    print(f"{'─' * 60}")
    for i, path in enumerate(found, 1):
        print(f"  {i:>{width}}.  {path}")
    print(f"{'─' * 60}\n")


def cmd_graph(input_file: str, rfc: str | None, force: bool = False, limit: int | None = None, output: str | None = None, max_cycles: int | None = None, max_depth: int | None = None, predecessors: bool = False, shortest: bool = False, min_size: int = 0, distinct_prev: bool = False) -> None:
    p = Path(input_file)
    cache_file = p.with_name(p.stem + "_graph.json")

    if not force and not limit and cache_file.exists():
        print(f"Loading graph from cache: {cache_file}")
        with open(cache_file) as f:
            G = nx.node_link_graph(json.load(f), directed=True)
    else:
        print("Building graph from XLSX files...")
        G = _build_graph(input_file, limit)
        if not limit:
            with open(cache_file, "w") as f:
                json.dump(nx.node_link_data(G), f)
            print(f"Graph cached to: {cache_file}")

    if rfc and predecessors:
        if rfc not in G.nodes():
            print(f"RFC not found in graph: {rfc}")
            return
        preds = [(p, G[p][rfc]) for p in G.predecessors(rfc)]
        if not preds:
            print(f"No predecessors found for RFC: {rfc}")
            return
        width = len(str(len(preds)))
        print(f"\n{'─' * 60}")
        print(f"  {len(preds)} predecessor(s) for {rfc}")
        print(f"{'─' * 60}")
        for i, (p, data) in enumerate(sorted(preds, key=lambda x: x[1].get("monto_efectivo", 0), reverse=True), 1):
            ef = data.get("monto_efectivo", 0)
            esp = data.get("monto_especie", 0)
            print(f"  {i:>{width}}.  {p}  ef:{ef:,.0f}  esp:{esp:,.0f}")
        print(f"{'─' * 60}\n")
        return

    if rfc:
        if rfc not in G.nodes():
            print(f"No cycle found for RFC: {rfc}")
            return
        scc = next((c for c in nx.strongly_connected_components(G) if rfc in c), None)
        if scc is None or len(scc) < 2:
            print(f"No cycle found for RFC: {rfc}")
            return
        subG = G.subgraph(scc)
        found = []
        if distinct_prev:
            gen = _shortest_cycles_distinct_prev(subG, rfc, max_cycles)
        elif shortest:
            gen = _shortest_cycles_through(subG, rfc, max_cycles)
        else:
            gen = _cycles_through(subG, rfc, max_cycles, max_depth)
        for cycle_nodes in gen:
            if len(cycle_nodes) <= min_size:
                continue
            found.append(_format_cycle(cycle_nodes, rfc, G))
            print(f"Cycles found: {len(found)}", end="\r", flush=True)
        print()
        if max_cycles and len(found) >= max_cycles:
            print(f"(stopped at {max_cycles} cycles — use --max-cycles to increase)")
        if output:
            Path(output).write_text("\n".join(found) + "\n")
            print(f"Wrote {len(found)} cycle(s) to {output}")
        else:
            _print_cycles(found)
    else:
        all_rfcs = set(pl.read_csv(input_file, columns=["Rfc"])["Rfc"].to_list())
        graph_rfcs = all_rfcs & set(G.nodes())
        seen: set[frozenset] = set()
        found = []
        if shortest:
            min_len = None
            raw = []
            print("Scanning graph for shortest cycles...", end="\r", flush=True)
            for cycle in nx.simple_cycles(G, length_bound=max_depth):
                key = frozenset(cycle)
                if key in seen:
                    continue
                seen.add(key)
                if len(cycle) <= min_size:
                    continue
                start = next((n for n in cycle if n in graph_rfcs), None)
                if start is None:
                    continue
                if min_len is None or len(cycle) < min_len:
                    min_len = len(cycle)
                    raw = [(cycle, start)]
                elif len(cycle) == min_len:
                    raw.append((cycle, start))
                    if max_cycles and len(raw) >= max_cycles:
                        break
                print(f"Scanning graph for shortest cycles: {len(raw)} found (len={min_len})...", end="\r", flush=True)
            found = [_format_cycle(c, s, G) for c, s in raw]
        else:
            print("Scanning graph for cycles...", end="\r", flush=True)
            for cycle in nx.simple_cycles(G):
                key = frozenset(cycle)
                if key in seen:
                    continue
                seen.add(key)
                if len(cycle) <= min_size:
                    continue
                start = next((n for n in cycle if n in graph_rfcs), None)
                if start is None:
                    continue
                found.append(_format_cycle(cycle, start, G))
                print(f"Scanning graph for cycles: {len(found)} found...", end="\r", flush=True)
                if max_cycles and len(found) >= max_cycles:
                    break
            if max_cycles and len(found) >= max_cycles:
                print(f"(stopped at {max_cycles} cycles — use --max-cycles to increase)")
        print()
        if not found:
            print("No cycles found in the graph.")
            return
        if output:
            Path(output).write_text("\n".join(found) + "\n")
            print(f"Wrote {len(found)} cycle(s) to {output}")
        else:
            _print_cycles(found)


def main():
    parser = argparse.ArgumentParser(description="Analyze Mexican foundation transparency data")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_search = subparsers.add_parser("search", help="Search by keyword and export Destino de donativos")
    p_search.add_argument("--input-file", required=True)
    p_search.add_argument("--keyword", required=True)
    p_search.add_argument("--output", default="destino_donativos.csv")
    p_search.add_argument("--limit", type=int, default=None, help="Process only the first N matched files")

    p_graph = subparsers.add_parser("graph", help="Find donation cycles for an RFC")
    p_graph.add_argument("--input-file", required=True)
    p_graph.add_argument("--rfc", default=None, help="RFC to check; omit to scan all RFCs")
    p_graph.add_argument("--force", action="store_true", help="Rebuild graph ignoring cache")
    p_graph.add_argument("--limit", type=int, default=None, help="Process only the first N files (skips cache write)")
    p_graph.add_argument("--output", default=None, help="Save results to file instead of printing")
    p_graph.add_argument("--max-cycles", type=int, default=100, help="Max cycles to return per RFC (default 100; 0 = unlimited)")
    p_graph.add_argument("--max-depth", type=int, default=8, help="Max cycle length in hops (default 8; 0 = unlimited)")
    p_graph.add_argument("--predecessors", action="store_true", help="List all RFCs that donate directly to --rfc")
    p_graph.add_argument("--shortest", action="store_true", help="Return only the shortest cycles for --rfc")
    p_graph.add_argument("--greater-than", type=int, default=0, dest="min_size", metavar="N", help="Only return cycles with more than N nodes")
    p_graph.add_argument("--distinct-prev", action="store_true", help="Return shortest cycle per distinct direct predecessor (requires --rfc)")

    args = parser.parse_args()
    if args.command == "search":
        cmd_search(args.input_file, args.keyword, args.output, args.limit)
    elif args.command == "graph":
        max_cycles = args.max_cycles if args.max_cycles != 0 else None
        max_depth = args.max_depth if args.max_depth != 0 else None
        cmd_graph(args.input_file, args.rfc, args.force, args.limit, args.output, max_cycles, max_depth, args.predecessors, args.shortest, args.min_size, args.distinct_prev)


if __name__ == "__main__":
    main()
