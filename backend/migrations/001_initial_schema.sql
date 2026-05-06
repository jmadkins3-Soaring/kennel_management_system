-- Soaring Heights KMS - Initial Schema
-- Applied automatically on startup via migration runner in main.py
-- All tables use TEXT UUIDs as primary keys. JSON blobs stored as JSON-typed columns.

CREATE TABLE IF NOT EXISTS staff_users (
    user_id     TEXT PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS owners (
    owner_id                TEXT PRIMARY KEY,
    first_name              TEXT NOT NULL,
    last_name               TEXT NOT NULL,
    alternate_name          TEXT,
    phone_number            TEXT NOT NULL,
    sms_number              TEXT,
    email                   TEXT NOT NULL,
    emergency_contact_name  TEXT,
    emergency_contact_phone TEXT,
    vet_name                TEXT,
    vet_phone               TEXT,
    notes                   TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
    archived                INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_owners_last_name ON owners(last_name);

CREATE TABLE IF NOT EXISTS dogs (
    dog_id              TEXT PRIMARY KEY,
    owner_id            TEXT NOT NULL REFERENCES owners(owner_id),
    name                TEXT NOT NULL,
    breed               TEXT NOT NULL,
    description         TEXT,
    size_class          TEXT NOT NULL CHECK (size_class IN ('XS','S','M','L','XL')),
    weight_lbs          REAL,
    date_of_birth       TEXT,
    medical_status      TEXT NOT NULL DEFAULT 'Healthy'
                            CHECK (medical_status IN ('Healthy','Injured','Quarantine','On Medication','Other')),
    medical_notes       TEXT,
    vaccination_records JSON,
    photo_url           TEXT,
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    archived            INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_dogs_owner_id ON dogs(owner_id);

CREATE TABLE IF NOT EXISTS kennels (
    kennel_id               TEXT PRIMARY KEY,
    kennel_number           TEXT NOT NULL UNIQUE,
    kennel_type             TEXT NOT NULL,
    max_size_class          TEXT NOT NULL CHECK (max_size_class IN ('XS','S','M','L','XL')),
    sqft                    REAL NOT NULL,
    features                TEXT,
    description             TEXT,
    active                  INTEGER NOT NULL DEFAULT 1,
    provisioned_from_config INTEGER NOT NULL DEFAULT 0,
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_kennels_number ON kennels(kennel_number);

CREATE TABLE IF NOT EXISTS kennel_holds (
    hold_id     TEXT PRIMARY KEY,
    kennel_id   TEXT NOT NULL REFERENCES kennels(kennel_id),
    start_date  TEXT NOT NULL,
    end_date    TEXT NOT NULL,
    reason      TEXT,
    created_by  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    released_at TEXT,
    released_by TEXT,
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_kennel_holds_kennel ON kennel_holds(kennel_id, active);

CREATE TABLE IF NOT EXISTS reservations (
    reservation_id      TEXT PRIMARY KEY,
    dog_id              TEXT NOT NULL REFERENCES dogs(dog_id),
    kennel_id           TEXT NOT NULL REFERENCES kennels(kennel_id),
    dropoff_datetime    TEXT NOT NULL,
    pickup_datetime     TEXT,
    pickup_open_ended   INTEGER NOT NULL DEFAULT 0,
    pickup_overdue_alerted INTEGER NOT NULL DEFAULT 0,
    checkin_datetime    TEXT,
    checkout_datetime   TEXT,
    checkin_staff       TEXT,
    checkout_staff      TEXT,
    medical_acknowledged INTEGER NOT NULL DEFAULT 0,
    checkout_healthy    INTEGER,
    checkout_notes      TEXT,
    notes               TEXT,
    cancelled           INTEGER NOT NULL DEFAULT 0,
    cancel_requested_by TEXT,
    cancel_confirmed_by TEXT,
    override_log        JSON,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reservations_dog ON reservations(dog_id);
CREATE INDEX IF NOT EXISTS idx_reservations_kennel ON reservations(kennel_id);
CREATE INDEX IF NOT EXISTS idx_reservations_dates ON reservations(dropoff_datetime, pickup_datetime);

CREATE TABLE IF NOT EXISTS bills (
    bill_id             TEXT PRIMARY KEY,
    reservation_id      TEXT NOT NULL REFERENCES reservations(reservation_id),
    billing_cycle       INTEGER NOT NULL DEFAULT 1,
    cycle_start_date    TEXT NOT NULL,
    cycle_end_date      TEXT NOT NULL,
    line_items          JSON,
    subtotal            REAL NOT NULL DEFAULT 0,
    total_discounts     REAL NOT NULL DEFAULT 0,
    total_due           REAL NOT NULL DEFAULT 0,
    paid                INTEGER NOT NULL DEFAULT 0,
    paid_datetime       TEXT,
    paid_confirmed_by   TEXT,
    receipt_emailed     INTEGER NOT NULL DEFAULT 0,
    receipt_pdf_path    TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_bills_reservation ON bills(reservation_id);

CREATE TABLE IF NOT EXISTS activity_types (
    activity_type_id            TEXT PRIMARY KEY,
    name                        TEXT NOT NULL UNIQUE,
    qualifies_for_pacfa_exception INTEGER NOT NULL DEFAULT 0,
    active                      INTEGER NOT NULL DEFAULT 1,
    created_at                  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS activities (
    activity_id                 TEXT PRIMARY KEY,
    reservation_id              TEXT NOT NULL REFERENCES reservations(reservation_id),
    incident_id                 TEXT REFERENCES incidents(incident_id),
    activity_type               TEXT NOT NULL,
    scheduled_date              TEXT NOT NULL,
    performed_datetime          TEXT,
    performed_by                TEXT,
    qualifies_for_pacfa_exception INTEGER NOT NULL DEFAULT 0,
    notes                       TEXT,
    created_at                  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_activities_reservation ON activities(reservation_id);
CREATE INDEX IF NOT EXISTS idx_activities_scheduled ON activities(scheduled_date);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id         TEXT PRIMARY KEY,
    dog_id              TEXT NOT NULL REFERENCES dogs(dog_id),
    reservation_id      TEXT NOT NULL REFERENCES reservations(reservation_id),
    incident_type       TEXT NOT NULL CHECK (incident_type IN ('Behavioral','Injury','Medical','EscapeAttempt','Other')),
    description         TEXT NOT NULL,
    occurred_datetime   TEXT NOT NULL,
    reported_by         TEXT NOT NULL,
    visible_to_owner    INTEGER NOT NULL DEFAULT 0,
    owner_notified      INTEGER NOT NULL DEFAULT 0,
    resolved            INTEGER NOT NULL DEFAULT 0,
    resolved_datetime   TEXT,
    resolved_by         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_incidents_dog ON incidents(dog_id, resolved);
CREATE INDEX IF NOT EXISTS idx_incidents_reservation ON incidents(reservation_id);

CREATE TABLE IF NOT EXISTS issues (
    issue_id            TEXT PRIMARY KEY,
    kennel_id           TEXT NOT NULL REFERENCES kennels(kennel_id),
    issue_type          TEXT NOT NULL CHECK (issue_type IN ('Maintenance','Safety','Cleanliness','Equipment','Other')),
    description         TEXT NOT NULL,
    reported_by         TEXT NOT NULL,
    reported_datetime   TEXT NOT NULL,
    resolved            INTEGER NOT NULL DEFAULT 0,
    resolved_datetime   TEXT,
    resolved_by         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_issues_kennel ON issues(kennel_id, resolved);

CREATE TABLE IF NOT EXISTS portal_tokens (
    token_id        TEXT PRIMARY KEY,
    owner_id        TEXT NOT NULL REFERENCES owners(owner_id),
    token_hash      TEXT NOT NULL UNIQUE,
    issued_at       TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at      TEXT NOT NULL,
    used_at         TEXT,
    revoked         INTEGER NOT NULL DEFAULT 0
)
