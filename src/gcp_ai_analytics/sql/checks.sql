-- Latest observation per cadence slot; unknown is not known monitoring coverage.
WITH observations AS (
  SELECT c.*, CAST(FLOOR(TIMESTAMP_DIFF(c.observed_at, @window_start, MICROSECOND)
    / (s.check_interval_seconds * 1000000.0)) AS INT64) AS slot
  FROM `{{checks}}` AS c JOIN UNNEST(@services) AS s USING (service_id)
  WHERE c.observed_at >= @window_start AND c.observed_at < @as_of
), slots AS (
  SELECT * FROM observations
  QUALIFY ROW_NUMBER() OVER (PARTITION BY service_id, slot
    ORDER BY observed_at DESC, event_id DESC) = 1
), counts AS (
  SELECT service_id, COUNT(*) AS observed_slots,
    COUNTIF(status IN ('up', 'down')) AS known_status_slots,
    COUNTIF(status = 'up') AS up_slots, COUNTIF(status = 'down') AS down_slots,
    COUNTIF(status = 'unknown') AS unknown_slots
  FROM slots GROUP BY service_id
), raw_counts AS (
  SELECT service_id, COUNT(*) AS raw_observations FROM observations GROUP BY service_id
), latest AS (
  SELECT service_id, status, latency_ms FROM `{{checks}}` WHERE observed_at < @as_of
  QUALIFY ROW_NUMBER() OVER (PARTITION BY service_id ORDER BY observed_at DESC, event_id DESC) = 1
), combined AS (
  SELECT s.service_id,
    CAST(CEIL(TIMESTAMP_DIFF(@as_of, @window_start, MICROSECOND)
      / (s.check_interval_seconds * 1000000.0)) AS INT64) AS expected_slots,
    COALESCE(r.raw_observations, 0) AS raw_observations,
    COALESCE(c.observed_slots, 0) AS observed_slots,
    COALESCE(c.known_status_slots, 0) AS known_status_slots,
    COALESCE(c.up_slots, 0) AS up_slots, COALESCE(c.down_slots, 0) AS down_slots,
    COALESCE(c.unknown_slots, 0) AS unknown_slots,
    l.status AS latest_status, l.latency_ms AS latest_latency_ms
  FROM UNNEST(@services) AS s
  LEFT JOIN counts AS c USING (service_id)
  LEFT JOIN raw_counts AS r USING (service_id)
  LEFT JOIN latest AS l USING (service_id)
)
SELECT *, expected_slots - observed_slots AS missing_slots,
  SAFE_DIVIDE(100.0 * up_slots, known_status_slots) AS sampled_success_pct,
  SAFE_DIVIDE(100.0 * known_status_slots, expected_slots) AS monitoring_coverage_pct
FROM combined ORDER BY service_id
