-- Completed cohort uses finish time; pending jobs include carry-in before window_start.
WITH included AS (
  SELECT *, status IN ('succeeded', 'failed') AS completed,
    TIMESTAMP_DIFF(finished_at, started_at, MICROSECOND) / 1000000.0 AS duration_seconds
  FROM `{{jobs}}`
  WHERE started_at < @as_of AND (
    (status IN ('succeeded', 'failed') AND finished_at >= @window_start AND finished_at < @as_of)
    OR status IN ('running', 'blocked'))
), counts AS (
  SELECT s.service_id,
    COUNTIF(j.completed) AS completed_runs,
    COUNTIF(j.status = 'succeeded') AS succeeded_runs,
    COUNTIF(j.status = 'failed') AS failed_runs,
    COUNTIF(j.status = 'running') AS running_runs,
    COUNTIF(j.status = 'blocked') AS blocked_runs,
    COALESCE(SUM(j.attempts - 1), 0) AS retries,
    COALESCE(SUM(IF(j.completed, j.attempts - 1, 0)), 0) AS completed_run_retries,
    COALESCE(SUM(IF(NOT j.completed, j.attempts - 1, 0)), 0) AS pending_run_retries,
    COUNTIF(NOT j.completed AND TIMESTAMP_DIFF(@as_of, j.started_at, MICROSECOND)
      > s.job_stale_after_hours * 3600000000.0) AS stale_pending_runs
  FROM UNNEST(@services) AS s LEFT JOIN included AS j USING (service_id)
  GROUP BY s.service_id
), slowest AS (
  SELECT service_id, job_id, duration_seconds FROM included WHERE completed
  QUALIFY ROW_NUMBER() OVER (PARTITION BY service_id ORDER BY duration_seconds DESC, event_id DESC) = 1
), oldest AS (
  SELECT service_id, job_id, started_at FROM included WHERE NOT completed
  QUALIFY ROW_NUMBER() OVER (PARTITION BY service_id ORDER BY started_at, event_id) = 1
), categories AS (
  SELECT service_id, COALESCE(error_category, 'unspecified') AS category, COUNT(*) AS count
  FROM included WHERE status = 'failed' GROUP BY service_id, category
), category_arrays AS (
  SELECT service_id, ARRAY_AGG(STRUCT(category, count) ORDER BY category) AS failure_categories
  FROM categories GROUP BY service_id
)
SELECT c.*, SAFE_DIVIDE(100.0 * c.succeeded_runs, c.completed_runs) AS success_pct,
  COALESCE(a.failure_categories, ARRAY<STRUCT<category STRING, count INT64>>[]) AS failure_categories,
  slowest.job_id AS slowest_completed_job_id,
  slowest.duration_seconds AS slowest_completed_duration_seconds,
  oldest.job_id AS oldest_pending_job_id,
  TIMESTAMP_DIFF(@as_of, oldest.started_at, MICROSECOND) / 3600000000.0 AS oldest_pending_age_hours,
  s.job_stale_after_hours AS pending_age_target_hours
FROM counts AS c JOIN UNNEST(@services) AS s USING (service_id)
LEFT JOIN slowest USING (service_id) LEFT JOIN oldest USING (service_id)
LEFT JOIN category_arrays AS a USING (service_id)
ORDER BY service_id
