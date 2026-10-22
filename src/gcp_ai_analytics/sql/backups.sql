-- Last success and latest attempt are separate evidence; checksum is not restore proof.
WITH latest AS (
  SELECT * FROM `{{backups}}` WHERE completed_at < @as_of
  QUALIFY ROW_NUMBER() OVER (PARTITION BY service_id ORDER BY completed_at DESC, event_id DESC) = 1
), success AS (
  SELECT * FROM `{{backups}}` WHERE completed_at < @as_of AND outcome = 'success'
  QUALIFY ROW_NUMBER() OVER (PARTITION BY service_id ORDER BY completed_at DESC, event_id DESC) = 1
)
SELECT s.service_id, s.backup_max_age_hours AS max_age_hours,
  a.completed_at AS latest_attempt_at, a.outcome AS latest_attempt_outcome,
  b.completed_at AS last_success_at,
  TIMESTAMP_DIFF(@as_of, b.completed_at, MICROSECOND) / 3600000000.0 AS last_success_age_hours,
  b.verification = 'checksum' AS last_success_checksum_verified,
  TIMESTAMP_DIFF(@as_of, b.completed_at, MICROSECOND)
    > s.backup_max_age_hours * 3600000000.0 AS is_overdue
FROM UNNEST(@services) AS s
LEFT JOIN latest AS a USING (service_id) LEFT JOIN success AS b USING (service_id)
ORDER BY service_id
