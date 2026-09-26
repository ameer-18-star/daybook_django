"""
Swimlane timeline layout — the interval-partitioning + column-packing
algorithm behind the day view. Deliberately pure Python (no Django
imports) so it's testable in isolation from the ORM/request cycle.
"""

DEFAULT_DURATION_MINUTES = 30  # visual fallback when a habit has no duration set


def compute_timeline_layout(events, window_start, window_end):
    """
    events: list of dicts, each with at least 'start' and 'duration'
            (both in minutes-from-midnight / minutes). Any other keys
            are carried through untouched.
    window_start, window_end: minutes-from-midnight bounding the
            rendered day (e.g. 6*60 to 22*60 for a 6am-10pm view).

    Returns a new list (same dicts, mutated with layout keys) sorted
    by start time.
    """
    window_total = window_end - window_start
    if window_total <= 0:
        return []

    working = []
    for item in events:
        start = item['start']
        end = start + item['duration']
        clipped_start = max(start, window_start)
        clipped_end = min(end, window_end)
        if clipped_end <= clipped_start:
            clipped_start = min(max(clipped_start, window_start), window_end - 1)
            clipped_end = clipped_start + 1
        working.append({**item, 'clipped_start': clipped_start, 'clipped_end': clipped_end})

    working.sort(key=lambda e: (e['clipped_start'], -e['clipped_end']))

    clusters = []
    current_cluster = []
    cluster_max_end = None
    for e in working:
        if current_cluster and e['clipped_start'] >= cluster_max_end:
            clusters.append(current_cluster)
            current_cluster = []
            cluster_max_end = None
        current_cluster.append(e)
        cluster_max_end = e['clipped_end'] if cluster_max_end is None else max(cluster_max_end, e['clipped_end'])
    if current_cluster:
        clusters.append(current_cluster)

    result = []
    for cluster in clusters:
        columns_last_end = []
        for e in cluster:
            placed = False
            for col_idx, last_end in enumerate(columns_last_end):
                if e['clipped_start'] >= last_end:
                    columns_last_end[col_idx] = e['clipped_end']
                    e['lane'] = col_idx
                    placed = True
                    break
            if not placed:
                columns_last_end.append(e['clipped_end'])
                e['lane'] = len(columns_last_end) - 1
        total_lanes = len(columns_last_end)
        for e in cluster:
            e['cluster_lanes'] = total_lanes
            result.append(e)

    for e in result:
        e['top_pct'] = round((e['clipped_start'] - window_start) / window_total * 100, 3)
        e['height_pct'] = round((e['clipped_end'] - e['clipped_start']) / window_total * 100, 3)
        e['left_pct'] = round(e['lane'] / e['cluster_lanes'] * 100, 3)
        e['width_pct'] = round(100 / e['cluster_lanes'], 3)

    return result
