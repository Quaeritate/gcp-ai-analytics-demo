WITH latest AS (
  SELECT * FROM `{{restore_tests}}` WHERE completed_at < @as_of
  QUALIFY ROW_NUMBER() OVER (PARTITION BY service_id ORDER BY completed_at DESC, event_id DESC) = 1
), passed AS (
  SELECT * FROM `{{restore_tests}}` WHERE completed_at < @as_of AND outcome = 'passed'
  QUALIFY ROW_NUMBER() OVER (PARTITION BY service_id ORDER BY completed_at DESC, event_id DESC) = 1
)
SELECT s.service_id, s.restore_max_age_days,
  a.completed_at AS latest_restore_at, a.outcome AS latest_restore_outcome,
  p.completed_at AS last_passed_restore_at,
  TIMESTAMP_DIFF(@as_of, p.completed_at, MICROSECOND) / 86400000000.0
    AS last_passed_restore_age_days,
  TIMESTAMP_DIFF(@as_of, p.completed_at, MICROSECOND) / 86400000000.0
    > s.restore_max_age_days AS restore_is_overdue
FROM UNNEST(@services) AS s
LEFT JOIN latest AS a USING (service_id) LEFT JOIN passed AS p USING (service_id)
ORDER BY service_id
