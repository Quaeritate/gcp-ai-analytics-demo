-- Latest source history can predate the report start. Cutoff is always exclusive.
WITH checks AS (
  SELECT service_id, MAX(observed_at) AS observed_at FROM `{{checks}}`
  WHERE observed_at < @as_of GROUP BY service_id
), resources AS (
  SELECT service_id, MAX(observed_at) AS observed_at FROM `{{resources}}`
  WHERE observed_at < @as_of GROUP BY service_id
)
SELECT s.service_id,
  c.observed_at AS checks_latest_observed_at,
  TIMESTAMP_DIFF(@as_of, c.observed_at, MICROSECOND) / 3600000000.0 AS checks_latest_age_hours,
  TIMESTAMP_DIFF(@as_of, c.observed_at, MICROSECOND)
    <= 2 * s.check_interval_seconds * 1000000.0 AS checks_is_fresh,
  2 * s.check_interval_seconds AS checks_freshness_limit_seconds,
  r.observed_at AS resources_latest_observed_at,
  TIMESTAMP_DIFF(@as_of, r.observed_at, MICROSECOND) / 3600000000.0 AS resources_latest_age_hours,
  TIMESTAMP_DIFF(@as_of, r.observed_at, MICROSECOND)
    <= 2 * s.check_interval_seconds * 1000000.0 AS resources_is_fresh,
  2 * s.check_interval_seconds AS resources_freshness_limit_seconds
FROM UNNEST(@services) AS s
LEFT JOIN checks AS c USING (service_id) LEFT JOIN resources AS r USING (service_id)
ORDER BY service_id
