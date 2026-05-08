-- Migration 002: Add missing indexes identified in code review.
-- All statements use IF NOT EXISTS so this is safe to re-apply.

-- reservations: cancelled is filtered on almost every query
CREATE INDEX IF NOT EXISTS idx_reservations_cancelled ON reservations(cancelled);

-- bills: paid status is filtered for overdue-bill checks and reports
CREATE INDEX IF NOT EXISTS idx_bills_paid ON bills(paid);

-- activities: FK to incidents and activity_type filtered for PACFA qualifying checks
CREATE INDEX IF NOT EXISTS idx_activities_incident_id ON activities(incident_id);
CREATE INDEX IF NOT EXISTS idx_activities_activity_type ON activities(activity_type);

-- soft-delete filters: every list endpoint filters on archived / active
CREATE INDEX IF NOT EXISTS idx_dogs_archived ON dogs(archived);
CREATE INDEX IF NOT EXISTS idx_owners_archived ON owners(archived);
CREATE INDEX IF NOT EXISTS idx_kennels_active ON kennels(active);

-- portal_tokens: token cleanup queries filter on expires_at
CREATE INDEX IF NOT EXISTS idx_portal_tokens_expires_at ON portal_tokens(expires_at);
