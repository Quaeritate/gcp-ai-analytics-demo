WITH latest AS (
  SELECT * FROM `{{resources}}` WHERE observed_at < @as_of
  QUALIFY ROW_NUMBER() OVER (PARTITION BY service_id ORDER BY observed_at DESC, event_id DESC) = 1
), combined AS (
  SELECT s.service_id, r.observed_at AS latest_observed_at,
    TIMESTAMP_DIFF(@as_of, r.observed_at, MICROSECOND) / 3600000000.0 AS latest_age_hours,
    TIMESTAMP_DIFF(@as_of, r.observed_at, MICROSECOND)
      <= 2 * s.check_interval_seconds * 1000000.0 AS is_fresh,
    2 * s.check_interval_seconds AS freshness_limit_seconds,
    r.cpu_pct, r.memory_pct, r.disk_used_bytes, r.disk_total_bytes,
    SAFE_DIVIDE(100.0 * r.disk_used_bytes, r.disk_total_bytes) AS disk_used_pct,
    r.disk_free_inodes_pct, r.pool_health, r.disk_health,
    [STRUCT('cpu_pct' AS name, r.cpu_pct IS NOT NULL AS measured),
     STRUCT('memory_pct', r.memory_pct IS NOT NULL),
     STRUCT('disk_used_bytes', r.disk_used_bytes IS NOT NULL),
     STRUCT('disk_total_bytes', r.disk_total_bytes IS NOT NULL),
     STRUCT('disk_free_inodes_pct', r.disk_free_inodes_pct IS NOT NULL),
     STRUCT('pool_health', r.pool_health IS NOT NULL),
     STRUCT('disk_health', r.disk_health IS NOT NULL)] AS fields
  FROM UNNEST(@services) AS s LEFT JOIN latest AS r USING (service_id)
)
SELECT * EXCEPT(fields),
  ARRAY(SELECT field.name FROM UNNEST(fields) AS field WITH OFFSET AS position
        WHERE field.measured ORDER BY position) AS measured_fields,
  ARRAY(SELECT field.name FROM UNNEST(fields) AS field WITH OFFSET AS position
        WHERE NOT field.measured ORDER BY position) AS missing_fields
FROM combined ORDER BY service_id
